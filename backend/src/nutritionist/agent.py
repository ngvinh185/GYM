"""Agent lập thực đơn theo ngày.

LLM chỉ chọn món + gram. Mọi phép cộng/nhân (protein, carb, fat, tiền) do tool
`calculate_menu` làm bằng code. Kết quả cuối cùng cũng được tính lại bằng code
để không phụ thuộc vào số LLM tự viết.

Cài đặt:  pip install langchain-openai
Biến môi trường:  OPENAI_API_KEY
"""
import json
import random
from dataclasses import dataclass
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import StructuredTool
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from nutritionist.user_information import User
from nutritionist.caculate import (
    MEAL_SPLIT,
    build_meal_targets,
    get_bmr,
    get_tdee,
    target_per_meal,
    target_protein_carb_fat,
)
from nutritionist.prompt import prompt as PROMPT_TEMPLATE

MODEL = "gpt-4.1-mini"
MAX_STEPS = 10                   # số vòng gọi tool tối đa
FOODS_PER_GROUP = 7              # số món random mỗi nhóm đưa vào prompt
DATA_PATH = Path(__file__).parent / "data.json"

# Sai số chấp nhận được (protein, carb, fat) - khớp với prompt
DAY_TOLERANCE = (8, 15, 8)
MEAL_TOLERANCE = (5, 10, 5)


# ----------------------------------------------------------------------------
# Dữ liệu thực phẩm
# ----------------------------------------------------------------------------
def load_foods(path: Path = DATA_PATH) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def sample_foods(foods: dict, n: int = FOODS_PER_GROUP, seed: int | None = None) -> dict:
    """Mỗi nhóm lấy ngẫu nhiên n món (không trùng)."""
    rng = random.Random(seed)
    return {group: rng.sample(items, min(n, len(items))) for group, items in foods.items()}


def build_food_tables(foods: dict) -> str:
    """Bảng text gọn cho prompt (bỏ trường 'nguon' để tiết kiệm token)."""
    lines = []
    for group, items in foods.items():
        lines.append(f"## {group}")
        lines.append("Món ăn | Protein (g) | Carb (g) | Fat (g) | Giá (VND)")
        for x in items:
            lines.append(f'{x["ten"]} | {x["protein"]} | {x["carb"]} | {x["fat"]} | {x["gia_100g"]}')
        lines.append("")
    return "\n".join(lines)


def build_lookup(foods: dict) -> dict:
    """ten -> thông tin món (kèm nhóm). Chỉ gồm các món đang có trong prompt."""
    return {x["ten"]: {**x, "nhom": group} for group, items in foods.items() for x in items}


# ----------------------------------------------------------------------------
# Tool: calculate_menu
# ----------------------------------------------------------------------------
@dataclass
class Context:
    lookup: dict           # các món được phép dùng
    day_target: tuple      # (protein, carb, fat) cả ngày
    meal_targets: list     # kết quả target_per_meal()
    budget: float          # VND / ngày


class MealItem(BaseModel):
    ten: str = Field(description="Tên món đúng như trong bảng thực phẩm")
    gram: float = Field(description="Khối lượng (gram), lớn hơn 0")


class Meal(BaseModel):
    bua: int = Field(description="Số thứ tự bữa, bắt đầu từ 1")
    mon_an: list[MealItem]


class CalculateMenuInput(BaseModel):
    meals: list[Meal] = Field(description="Danh sách các bữa trong ngày, theo thứ tự thời gian")


CALCULATE_DESCRIPTION = (
    "Tính chính xác protein, carb, fat và chi phí của thực đơn. Truyền vào danh sách các bữa, "
    "mỗi bữa gồm các món (tên đúng như trong bảng thực phẩm) và gram. Tool trả về macro từng món, "
    "tổng từng bữa, tổng cả ngày, độ chênh so với mục tiêu và ngân sách, cùng cờ cho biết "
    "đã đạt sai số hay chưa. Luôn dùng tool này thay vì tự cộng nhẩm."
)


TOOL_INSTRUCTIONS = """

# CÔNG CỤ TÍNH TOÁN (BẮT BUỘC)
Bạn có tool `calculate_menu`. KHÔNG tự cộng/nhân nhẩm bất kỳ con số nào.
Quy trình:
1. Chọn món và gram cho tất cả các bữa, gọi `calculate_menu` với toàn bộ thực đơn.
2. Đọc kết quả: nếu có `loi`, hoặc `dat_sai_so` của bữa/ngày = false, hoặc `trong_ngan_sach` = false,
   hãy chỉnh gram hoặc đổi món rồi gọi lại tool.
3. Khi đạt (hoặc không thể đạt thêm do ngân sách/bảng món), trả về JSON cuối cùng theo ĐỊNH DẠNG ĐẦU RA.
   Các con số trong JSON phải lấy từ kết quả tool gần nhất. Hệ thống sẽ tính lại các số này bằng code,
   nên điều quan trọng nhất là tên món và gram.
"""


def calc_menu(meals: list, ctx: Context) -> dict:
    """Tính macro/tiền từ (ten, gram). Dùng cho cả tool và bước kiểm tra cuối."""
    errors: list[str] = []
    if len(meals) != len(ctx.meal_targets):
        errors.append(f"Cần đúng {len(ctx.meal_targets)} bữa, hiện có {len(meals)} bữa")

    day = {"protein_g": 0.0, "carb_g": 0.0, "fat_g": 0.0, "chi_phi_vnd": 0.0}
    out_meals = []

    for m in meals:
        bua = m.get("bua")
        total = {"protein_g": 0.0, "carb_g": 0.0, "fat_g": 0.0, "chi_phi_vnd": 0.0}
        items_out = []

        for it in m.get("mon_an", []):
            ten, gram = it.get("ten"), it.get("gram")
            food = ctx.lookup.get(ten)
            if food is None:
                errors.append(f"Bữa {bua}: món '{ten}' không có trong bảng thực phẩm")
                continue
            if not isinstance(gram, (int, float)) or gram <= 0:
                errors.append(f"Bữa {bua}: gram của '{ten}' không hợp lệ ({gram})")
                continue
            k = gram / 100
            p, c, f, cost = food["protein"] * k, food["carb"] * k, food["fat"] * k, food["gia_100g"] * k
            total["protein_g"] += p
            total["carb_g"] += c
            total["fat_g"] += f
            total["chi_phi_vnd"] += cost
            items_out.append({
                "ten": ten, "nhom": food["nhom"], "gram": gram,
                "protein_g": round(p, 1), "carb_g": round(c, 1),
                "fat_g": round(f, 1), "gia_vnd": round(cost),
            })

        meal_out = {
            "bua": bua,
            "mon_an": items_out,
            "tong_bua": {
                "protein_g": round(total["protein_g"], 1),
                "carb_g": round(total["carb_g"], 1),
                "fat_g": round(total["fat_g"], 1),
                "chi_phi_vnd": round(total["chi_phi_vnd"]),
            },
        }

        idx = (bua or 0) - 1
        if 0 <= idx < len(ctx.meal_targets):
            mt = ctx.meal_targets[idx]
            dp = total["protein_g"] - mt["protein_g"]
            dc = total["carb_g"] - mt["carb_g"]
            df = total["fat_g"] - mt["fat_g"]
            meal_out["chenh_lech_so_voi_muc_tieu_bua"] = {
                "protein_g": round(dp, 1), "carb_g": round(dc, 1), "fat_g": round(df, 1),
            }
            meal_out["dat_sai_so"] = (
                abs(dp) <= MEAL_TOLERANCE[0] and abs(dc) <= MEAL_TOLERANCE[1] and abs(df) <= MEAL_TOLERANCE[2]
            )
        else:
            errors.append(f"Bữa số {bua} nằm ngoài khoảng 1-{len(ctx.meal_targets)}")
            meal_out["dat_sai_so"] = False

        for key in day:
            day[key] += total[key]
        out_meals.append(meal_out)

    tp, tc, tf = ctx.day_target
    dp, dc, df = day["protein_g"] - tp, day["carb_g"] - tc, day["fat_g"] - tf
    return {
        "bua_an": out_meals,
        "tong_ngay": {
            "protein_g": round(day["protein_g"], 1),
            "carb_g": round(day["carb_g"], 1),
            "fat_g": round(day["fat_g"], 1),
            "chi_phi_vnd": round(day["chi_phi_vnd"]),
        },
        "so_voi_muc_tieu": {
            "protein_chenh_lech_g": round(dp, 1),
            "carb_chenh_lech_g": round(dc, 1),
            "fat_chenh_lech_g": round(df, 1),
            "con_du_ngan_sach_vnd": round(ctx.budget - day["chi_phi_vnd"]),
        },
        "dat_sai_so_ngay": (
            abs(dp) <= DAY_TOLERANCE[0] and abs(dc) <= DAY_TOLERANCE[1] and abs(df) <= DAY_TOLERANCE[2]
        ),
        "trong_ngan_sach": day["chi_phi_vnd"] <= ctx.budget,
        "loi": errors,
    }


# ----------------------------------------------------------------------------
# Prompt
# ----------------------------------------------------------------------------
def render_prompt(template: str, values: dict) -> str:
    """Thay {{key}} bằng giá trị. Không dùng str.format vì JSON trong prompt có dấu { }."""
    for key, value in values.items():
        template = template.replace("{{" + key + "}}", str(value))
    return template


def extract_json(text: str) -> dict:
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"Không tìm thấy JSON trong phản hồi: {text[:200]}")
    return json.loads(text[start:end + 1])


# ----------------------------------------------------------------------------
# Agent
# ----------------------------------------------------------------------------
def plan_menu(user: User, seed: int | None = None) -> dict:
    if user["count_meal"] not in MEAL_SPLIT:
        raise ValueError(f"count_meal phải nằm trong {sorted(MEAL_SPLIT)}")

    sampled = sample_foods(load_foods(), FOODS_PER_GROUP, seed)
    protein, carb, fat = target_protein_carb_fat(user)
    meal_targets = target_per_meal(user)

    ctx = Context(
        lookup=build_lookup(sampled),
        day_target=(protein, carb, fat),
        meal_targets=meal_targets,
        budget=user["budget"],
    )

    system_prompt = render_prompt(PROMPT_TEMPLATE, {
        "gender": "nam" if user["gender"] else "nữ",
        "age": user["age"],
        "height_cm": user["height"],
        "weight_kg": user["weight"],
        "goal": user["goal"],
        "count_meal": user["count_meal"],
        "budget": round(user["budget"]),
        "bmr": round(get_bmr(user)),
        "tdee": round(get_tdee(user)),
        "target_protein_g": protein,
        "target_carb_g": carb,
        "target_fat_g": fat,
        "meal_targets": build_meal_targets(meal_targets),
        "food_tables": build_food_tables(sampled),
    }) + TOOL_INSTRUCTIONS

    # Tool gắn với ctx của request này (closure) nên không bị lẫn dữ liệu giữa các user
    def _calculate_menu(meals: list) -> dict:
        payload = [m.model_dump() if hasattr(m, "model_dump") else m for m in meals]
        return calc_menu(payload, ctx)

    calc_tool = StructuredTool.from_function(
        func=_calculate_menu,
        name="calculate_menu",
        description=CALCULATE_DESCRIPTION,
        args_schema=CalculateMenuInput,
    )

    llm = ChatOpenAI(model=MODEL, temperature=0.2, timeout=90, max_retries=2).bind_tools([calc_tool])
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content="Hãy lập thực đơn cả ngày theo thông tin ở trên."),
    ]
    final_text = None

    for _ in range(MAX_STEPS):
        ai = llm.invoke(messages)
        messages.append(ai)

        if not ai.tool_calls:
            final_text = ai.content if isinstance(ai.content, str) else "".join(
                part.get("text", "") if isinstance(part, dict) else str(part) for part in ai.content
            )
            break

        for tc in ai.tool_calls:
            try:
                result = calc_tool.invoke(tc["args"])
            except Exception as e:  # trả lỗi cho model tự sửa thay vì làm sập request
                result = {"loi": [f"Tool lỗi: {e}"]}
            messages.append(ToolMessage(
                content=json.dumps(result, ensure_ascii=False),
                tool_call_id=tc["id"],
                name=tc["name"],
            ))

    if final_text is None:
        raise RuntimeError(f"Agent chưa trả kết quả cuối sau {MAX_STEPS} vòng gọi tool")

    return finalize(extract_json(final_text), ctx)


def finalize(agent_json: dict, ctx: Context) -> dict:
    """Tính lại toàn bộ số bằng code từ (tên món, gram) mà agent chọn."""
    meals = [
        {
            "bua": b.get("bua"),
            "mon_an": [{"ten": i.get("ten"), "gram": i.get("gram")} for i in b.get("mon_an", [])],
        }
        for b in agent_json.get("bua_an", [])
    ]
    result = calc_menu(meals, ctx)
    result["dat_muc_tieu"] = result["dat_sai_so_ngay"] and result["trong_ngan_sach"] and not result["loi"]
    result["ghi_chu"] = agent_json.get("ghi_chu", "")
    return result


if __name__ == "__main__":
    demo_user: User = {
        "gender": True,
        "age": 25,
        "height": 170,
        "weight": 70,
        "activity_factor": 1.55,
        "count_meal": 3,
        "goal": "muscle_gain",
        "budget": 150000,
    }
    print(json.dumps(plan_menu(demo_user), ensure_ascii=False, indent=2))
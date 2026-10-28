import logging
import os
import uuid
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from threading import Lock
import time
import bcrypt
import jwt  # pip install pyjwt
import psycopg2
import psycopg2.extras
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from student_assitant.pdf.pdf_handle import _get_retriever
_get_retriever()  # khởi tạo sẵn để load embeddings và vectorstore ngay khi app start, tránh chậm khi gọi lần đầu
from student_assitant.config import DB_CONFIG
from student_assitant.assitant import Graph
from nutritionist.agent import plan_menu
from nutritionist.caculate import GOAL_CONFIG, MEAL_SPLIT

app = FastAPI(title="GymHeart Assistant API")

# Origin của trang web (không dùng "*" khi có header Authorization)
ALLOWED_ORIGINS = ["http://localhost:8000", "http://127.0.0.1:8000", "http://localhost:5500", "http://127.0.0.1:5500"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["POST", "GET"],
    allow_headers=["Authorization", "Content-Type"],
)

# ---------- JWT ----------
JWT_SECRET = os.environ["JWT_SECRET"]  # chuỗi ngẫu nhiên dài >= 32 ký tự, không commit lên git
JWT_ALGORITHM = "HS256"
SESSION_HOURS = 12  # khớp SESSION_DURATION_MS của auth.js

# Hash giả để so sánh khi email không tồn tại (tránh lộ email nào có tài khoản qua thời gian phản hồi)
_DUMMY_HASH = bcrypt.hashpw(b"dummy-password", bcrypt.gensalt())

USER_COLUMNS = (
    "id, email, full_name, phone, avatar_url, date_of_birth, gender, address, role, "
    "is_active, bio, specialization, years_of_experience, certification, "
    "requested_role, created_at, updated_at"
)


# ---------- Đăng nhập ----------
class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=128)


@app.post("/auth/login")
def login(req: LoginRequest):
    email = req.email.strip().lower()
    try:
        with closing(psycopg2.connect(**DB_CONFIG)) as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    f"SELECT {USER_COLUMNS}, password_hash FROM users WHERE email = %s LIMIT 1",
                    (email,),
                )
                row = cur.fetchone()
    except Exception:
        logging.exception("Lỗi DB khi đăng nhập")
        raise HTTPException(status_code=500, detail="Lỗi hệ thống")

    stored = (row["password_hash"] if row else None) or ""
    hash_bytes = stored.encode() if stored.startswith("$2") else _DUMMY_HASH
    try:
        ok = bcrypt.checkpw(req.password.encode()[:72], hash_bytes)
    except ValueError:
        ok = False

    if not row or not ok:
        raise HTTPException(status_code=401, detail="Email hoặc mật khẩu không đúng!")
    if not row["is_active"]:
        raise HTTPException(status_code=403, detail="Tài khoản đã bị vô hiệu hóa.")

    row.pop("password_hash", None)
    now = datetime.now(timezone.utc)
    exp = now + timedelta(hours=SESSION_HOURS)
    token = jwt.encode(
        {"sub": str(row["id"]), "iat": now, "exp": exp},
        JWT_SECRET,
        algorithm=JWT_ALGORITHM,
    )
    return {
        "token": token,
        "issued_at": int(now.timestamp() * 1000),
        "expires_at": int(exp.timestamp() * 1000),
        "user": row,
    }


# ---------- Xác thực mỗi request ----------
@dataclass
class CurrentUser:
    user_id: str
    role: str  # "USER" | "ADMIN" | "COACH"


def get_role_from_db(user_id: str) -> str | None:
    """Tra role thật của user_id trong bảng users (chỉ tài khoản đang active).
    Trả None nếu không tồn tại, bị vô hiệu hóa, hoặc lỗi kết nối.
    Mở connection riêng mỗi lần gọi (không dùng chung với sql_tools.py vì
    cursor đó chạy trong thread khác qua ThreadPoolExecutor)."""
    try:
        with closing(psycopg2.connect(**DB_CONFIG)) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT role FROM users WHERE id = %s AND is_active = true",
                    (user_id,),
                )
                row = cur.fetchone()
                return row[0] if row else None
    except Exception:
        logging.exception("Lỗi khi tra role cho user_id=%s", user_id)
        return None


def get_current_user(authorization: str | None = Header(default=None)) -> CurrentUser:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Thiếu token")

    token = authorization.removeprefix("Bearer ").strip()
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token đã hết hạn")
    except jwt.InvalidTokenError as e:
        print("JWT ERROR:", type(e).__name__, e)
        print("TOKEN HEAD:", token[:30], "| ALG:", JWT_ALGORITHM)
        raise HTTPException(status_code=401, detail="Token không hợp lệ")

    user_id = payload.get("sub")
    if not user_id:
        print("JWT PAYLOAD KHÔNG CÓ sub:", payload)
        raise HTTPException(status_code=401, detail="Token không hợp lệ")

    role = get_role_from_db(str(user_id))  # role luôn tra từ DB, không nằm trong token
    if role is None:
        raise HTTPException(status_code=401, detail="User không tồn tại hoặc đã bị vô hiệu hóa")

    return CurrentUser(user_id=str(user_id), role=role.upper())


# ---------- Cache Graph theo (user_id, role) ----------
# InMemorySaver nằm trong Graph, nên phải giữ cùng instance thì mới giữ được lịch sử hội thoại.
_graphs: dict[tuple[str, str], Graph] = {}
_lock = Lock()


def get_graph(user: CurrentUser) -> Graph:
    key = (user.user_id, user.role)
    with _lock:
        if key not in _graphs:
            _graphs[key] = Graph(user_role=user.role, user_id=user.user_id)
        return _graphs[key]


# ---------- Chat ----------
class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    session_id: str | None = None  # bỏ trống = tạo cuộc hội thoại mới


class ChatResponse(BaseModel):
    reply: str
    session_id: str


def extract_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):  # content blocks
        return "".join(
            b.get("text", "") if isinstance(b, dict) else str(b) for b in content
        )
    return str(content)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest, user: CurrentUser = Depends(get_current_user)):
    t0 = time.time()
    session_id = req.session_id or uuid.uuid4().hex
    # gắn user_id vào thread_id để user này không đọc được hội thoại của user khác
    thread_id = f"{user.user_id}:{session_id}"

    graph = get_graph(user)
    print(f"[chat] graph san sang sau {time.time()-t0:.1f}s", flush=True)
    try:
        result = graph.invoke(req.message, thread_id=thread_id)
        print("------------SQL TRACES------------")
        print(result['sql_traces'])
        print("------------DEEPAGENT CALLS------------")
        print(result['subagent_call'])
        print("------------MESSAGES------------")
        for m in result['messages']:
            print(m)
            print("-------------------")
    except Exception:
        logging.exception("Lỗi khi xử lý chat cho user_id=%s", user.user_id)
        raise HTTPException(status_code=500, detail="Lỗi xử lý yêu cầu")
    print(f"[chat] invoke xong sau {time.time()-t0:.1f}s", flush=True)

    reply = extract_text(result["messages"][-1].content)
    return ChatResponse(reply=reply, session_id=session_id)


# ---------- Nutritionist: lập thực đơn ----------
class MenuRequest(BaseModel):
    gender: bool = Field(description="True = nam, False = nữ")
    age: int = Field(ge=10, le=100)
    height: float = Field(ge=100, le=250, description="cm")
    weight: float = Field(ge=25, le=300, description="kg")
    activity_factor: float = Field(ge=1.2, le=1.9)
    count_meal: int = Field(description="Số bữa / ngày (1-6)")
    goal: str = Field(description="muscle_gain | fat_loss | recomp | maintain")
    budget: float = Field(gt=0, le=10_000_000, description="VND / ngày")
    seed: int | None = None  # cố định seed để random cùng bộ món (tuỳ chọn)


@app.post("/nutrition/menu")
def nutrition_menu(req: MenuRequest, user: CurrentUser = Depends(get_current_user)):
    if req.count_meal not in MEAL_SPLIT:
        raise HTTPException(status_code=422, detail=f"count_meal phải nằm trong {sorted(MEAL_SPLIT)}")
    if req.goal not in GOAL_CONFIG:
        raise HTTPException(status_code=422, detail=f"goal phải nằm trong {sorted(GOAL_CONFIG)}")

    profile = req.model_dump(exclude={"seed"})  # dict khớp TypedDict User
    t0 = time.time()
    try:
        # def (không async) nên FastAPI tự chạy trong threadpool, không chặn event loop
        result = plan_menu(profile, seed=req.seed)
    except Exception:
        logging.exception("Lỗi khi lập thực đơn cho user_id=%s", user.user_id)
        raise HTTPException(status_code=500, detail="Lỗi xử lý yêu cầu")
    print(f"[nutrition] xong sau {time.time()-t0:.1f}s", flush=True)
    return result


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host="0.0.0.0", port=8001, reload=True)
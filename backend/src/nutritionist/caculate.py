from nutritionist.user_information import User
GOAL_CONFIG = {
    # goal: (hệ số calo so với TDEE, protein g/kg, fat g/kg)
    "muscle_gain": (1.10, 2.2, 0.8),
    "fat_loss":    (0.80, 2.0, 0.6),
    "recomp":      (0.93, 2.2, 0.8),
    "maintain":    (1.00, 1.8, 0.9),
}

def get_bmr(user: User) -> float:
    base = 10 * user["weight"] + 6.25 * user["height"] - 5 * user["age"]
    return base + 5 if user["gender"] else base - 161

def get_tdee(user: User) -> float:
    return get_bmr(user) * user["activity_factor"]

def target_protein_carb_fat(user: User) -> tuple[float, float, float]:
    """Trả về (protein, carb, fat) tính bằng gram, cho CẢ NGÀY."""
    calorie_factor, protein_per_kg, fat_per_kg = GOAL_CONFIG.get(
        user["goal"], GOAL_CONFIG["maintain"]
    )

    target_kcal = get_tdee(user) * calorie_factor
    protein = user["weight"] * protein_per_kg
    fat = user["weight"] * fat_per_kg
    carb = max((target_kcal - protein * 4 - fat * 9) / 4, 0)

    return round(protein, 1), round(carb, 1), round(fat, 1)
  
MEAL_SPLIT = {
  1: [1.0],
  2: [0.5, 0.5],
  3: [0.30, 0.40, 0.30],
  4: [0.25, 0.35, 0.15, 0.25],
  5: [0.20, 0.10, 0.30, 0.10, 0.30],
  6: [0.20, 0.10, 0.25, 0.10, 0.25, 0.10],
}

def target_per_meal(user: User) -> list[dict]:
  protein, carb, fat = target_protein_carb_fat(user)
  split = MEAL_SPLIT[user["count_meal"]]   # nên kiểm tra count_meal nằm trong 1-6
  return [
    {
        "meal": i + 1,
        "ratio_percent": round(r * 100),
        "protein_g": round(protein * r, 1),
        "carb_g": round(carb * r, 1),
        "fat_g": round(fat * r, 1),
    }
    for i, r in enumerate(split)
  ]
def build_meal_targets(meals: list[dict]) -> str:
  lines = ["Bữa | Tỉ lệ | Protein (g) | Carb (g) | Fat (g)"]
  for m in meals:
      lines.append(f'{m["meal"]} | {m["ratio_percent"]}% | {m["protein_g"]} | {m["carb_g"]} | {m["fat_g"]}')
  return "\n".join(lines)
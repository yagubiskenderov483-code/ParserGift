import os
import json

# === Telegram bot ===
BOT_TOKEN = "8952681622:AAGEe2m5L6jWxlFcw-gF_NIl9UbGDTW33Vc"

# === Твой личный Telegram-аккаунт (нужен для MRKT и Portals) ===
API_ID = 36101343
API_HASH = "116195fa5e0459d25a9a6266b40807d7"

SESSION_NAME = "user_session"  # файл user_session.session появится после первого /start

# === Ценовые категории (в TON) ===
PRICE_TIERS = [
    ("🟢 Лёгкий", 2000, 5000),
    ("🟡 Средний", 5000, 10000),
    ("🔴 Сложный", 10000, 20000),
    ("💎 Хардкор", 20000, 60000),
]

def classify_price(price: float) -> str | None:
    for label, lo, hi in PRICE_TIERS:
        if lo <= price < hi:
            return label
    return None

# === Интервалы поллинга (сек) ===
POLL_INTERVAL_TONNEL = 5
POLL_INTERVAL_PORTALS = 5
POLL_INTERVAL_MRKT = 5

SEEN_STORE_PATH = "seen.json"
CHAT_ID_STORE_PATH = "chat_id.json"
PORTALS_AUTH_PATH = "portals_auth.json"

def load_json_value(path: str, key: str):
    if os.path.exists(path):
        try:
            with open(path, "r") as f:
                return json.load(f).get(key)
        except Exception:
            return None
    return None

def save_json_value(path: str, key: str, value):
    with open(path, "w") as f:
        json.dump({key: value}, f)

def load_chat_id() -> int | None:
    return load_json_value(CHAT_ID_STORE_PATH, "chat_id")

def save_chat_id(chat_id: int):
    save_json_value(CHAT_ID_STORE_PATH, "chat_id", chat_id)

def load_portals_auth() -> str | None:
    return load_json_value(PORTALS_AUTH_PATH, "authData")

def save_portals_auth(auth_data: str):
    save_json_value(PORTALS_AUTH_PATH, "authData", auth_data)

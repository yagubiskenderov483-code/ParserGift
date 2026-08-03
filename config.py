import os
import json

# === Telegram bot ===
BOT_TOKEN = "8952681622:AAGEe2m5L6jWxlFcw-gF_NIl9UbGDTW33Vc"

# === MRKT (нужен твой личный Telegram-аккаунт, не бот) ===
API_ID = 36101343
API_HASH = "116195fa5e0459d25a9a6266b40807d7"

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

# Файл для хранения id уже отправленных лотов
SEEN_STORE_PATH = "seen.json"

# Файл, куда бот сам сохранит chat_id после /start — вписывать руками не надо
CHAT_ID_STORE_PATH = "chat_id.json"

def load_chat_id() -> int | None:
    if os.path.exists(CHAT_ID_STORE_PATH):
        try:
            with open(CHAT_ID_STORE_PATH, "r") as f:
                return json.load(f).get("chat_id")
        except Exception:
            return None
    return None

def save_chat_id(chat_id: int):
    with open(CHAT_ID_STORE_PATH, "w") as f:
        json.dump({"chat_id": chat_id}, f)

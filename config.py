import json
import os

# Telegram bot
BOT_TOKEN = "8952681622:AAGEe2m5L6jWxlFcw-gF_NIl9UbGDTW33Vc"

# Personal Telegram account (Portals + MRKT)
API_ID = 36101343
API_HASH = "116195fa5e0459d25a9a6266b40807d7"

SESSION_NAME = "user_session"
MRKT_SESSION_NAME = "mrkt_session"

# Price tiers in TON
PRICE_MIN = 2000
PRICE_MAX = 60000
PRICE_TIERS = (
    ("🟢 Лёгкий", 2000, 5000),
    ("🟡 Средний", 5000, 10000),
    ("🔴 Сложный", 10000, 20000),
    ("💎 Хардкор", 20000, 60000),
)

# Near-instant polling
POLL_INTERVAL = 1
FETCH_LIMIT = 30
PORTALS_AUTH_REFRESH = 6 * 60 * 60

SEEN_PATH = "seen.json"
CHAT_ID_PATH = "chat_id.json"
PORTALS_AUTH_PATH = "portals_auth.json"


def classify_price(price: float) -> str | None:
    if price < PRICE_MIN or price > PRICE_MAX:
        return None
    for i, (label, lo, hi) in enumerate(PRICE_TIERS):
        last = i == len(PRICE_TIERS) - 1
        if lo <= price < hi or (last and price == hi):
            return label
    return None


def _load(path: str, key: str):
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f).get(key)
    except Exception:
        return None


def _save(path: str, key: str, value) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump({key: value}, f)


def load_chat_id() -> int | None:
    return _load(CHAT_ID_PATH, "chat_id")


def save_chat_id(chat_id: int) -> None:
    _save(CHAT_ID_PATH, "chat_id", chat_id)


def load_portals_auth() -> str | None:
    return _load(PORTALS_AUTH_PATH, "authData")


def save_portals_auth(auth_data: str) -> None:
    _save(PORTALS_AUTH_PATH, "authData", auth_data)

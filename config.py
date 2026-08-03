# === Telegram ===
BOT_TOKEN = "8952681622:AAGEe2m5L6jWxlFcw-gF_NIl9UbGDTW33Vc"
API_ID = 36101343
API_HASH = "116195fa5e0459d25a9a6266b40807d7"

SESSION = "user_session"
MRKT_SESSION = "mrkt_session"

# === Price bands (TON) ===
PRICE_MIN = 2000
PRICE_MAX = 60000
TIERS = (
    ("🟢 Лёгкий", 2000, 5000),
    ("🟡 Средний", 5000, 10000),
    ("🔴 Сложный", 10000, 20000),
    ("💎 Хардкор", 20000, 60000),
)

POLL_SEC = 1
LIMIT = 30

BUILD = "scratch-2026-08-03"


def tier(price: float) -> str | None:
    if price < PRICE_MIN or price > PRICE_MAX:
        return None
    for label, lo, hi in TIERS[:-1]:
        if lo <= price < hi:
            return label
    label, lo, hi = TIERS[-1]
    if lo <= price <= hi:
        return label
    return None

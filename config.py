BOT_TOKEN = "8952681622:AAGEe2m5L6jWxlFcw-gF_NIl9UbGDTW33Vc"
API_ID = 36101343
API_HASH = "116195fa5e0459d25a9a6266b40807d7"

SESSION = "user_session"
MRKT_SESSION = "mrkt_session"

PRICE_MIN = 2000
PRICE_MAX = 60000

# лёгкий 2-5к · средний 5-10к · сложный 10-20к · хардкор 20-60к
TIERS = [
    ("🟢 Лёгкий", 2000, 5000),
    ("🟡 Средний", 5000, 10000),
    ("🔴 Сложный", 10000, 20000),
    ("💎 Хардкор", 20000, 60000),
]

POLL_SEC = 1
LIMIT = 30
BUILD = "full-2026-08-03"


def price_tier(price: float) -> str | None:
    if price < PRICE_MIN or price > PRICE_MAX:
        return None
    for name, lo, hi in TIERS[:-1]:
        if lo <= price < hi:
            return name
    name, lo, hi = TIERS[-1]
    if lo <= price <= hi:
        return name
    return None

import os
import shutil

from amrkt import MarketClient

from adapters.base import Listing
from config import (
    API_HASH,
    API_ID,
    FETCH_LIMIT,
    MRKT_SESSION_NAME,
    PRICE_MAX,
    PRICE_MIN,
    SESSION_NAME,
)

SOURCE = "MRKT"
URL = "https://t.me/mrkt/app"

_client: MarketClient | None = None


def ensure_session() -> None:
    src = f"{SESSION_NAME}.session"
    dst = f"{MRKT_SESSION_NAME}.session"
    if os.path.exists(src) and not os.path.exists(dst):
        try:
            shutil.copy2(src, dst)
        except Exception as e:
            print(f"[mrkt] session copy: {e}")


async def _client_get() -> MarketClient:
    global _client
    if _client is None:
        ensure_session()
        _client = MarketClient(
            api_id=API_ID,
            api_hash=API_HASH,
            session_name=MRKT_SESSION_NAME,
        )
        await _client.__aenter__()
    return _client


async def fetch_latest(limit: int = FETCH_LIMIT) -> list[Listing]:
    try:
        client = await _client_get()
        feed = await client.get_feed()
    except Exception as e:
        print(f"[mrkt] {e}")
        return []

    out: list[Listing] = []
    for item in feed.items or []:
        if item.type != "listing":
            continue
        try:
            price = float(item.amount_ton)
            if price < PRICE_MIN or price > PRICE_MAX:
                continue
            out.append(
                Listing(
                    source=SOURCE,
                    item_id=str(item.id),
                    name=item.gift.title,
                    model=item.gift.model_title,
                    price=price,
                    url=URL,
                )
            )
            if len(out) >= limit:
                break
        except Exception:
            continue
    return out

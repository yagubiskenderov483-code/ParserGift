import os
import shutil
from amrkt import MarketClient
from adapters.base import Listing
from config import (
    API_ID, API_HASH, SESSION_NAME, MRKT_SESSION_NAME,
    PRICE_MIN, PRICE_MAX, FETCH_LIMIT,
)

SOURCE = "MRKT"

_client: MarketClient | None = None

def ensure_mrkt_session():
    """Копируем уже залогиненную user-сессию в mrkt_session, чтобы не логиниться дважды."""
    src = f"{SESSION_NAME}.session"
    dst = f"{MRKT_SESSION_NAME}.session"
    if os.path.exists(src) and not os.path.exists(dst):
        try:
            shutil.copy2(src, dst)
            journal = f"{SESSION_NAME}.session-journal"
            if os.path.exists(journal):
                shutil.copy2(journal, f"{MRKT_SESSION_NAME}.session-journal")
        except Exception as e:
            print(f"[mrkt] session copy error: {e}")

async def get_client() -> MarketClient:
    global _client
    if _client is None:
        ensure_mrkt_session()
        _client = MarketClient(
            api_id=API_ID,
            api_hash=API_HASH,
            session_name=MRKT_SESSION_NAME,
        )
        await _client.__aenter__()
    return _client

async def fetch_latest(limit: int = FETCH_LIMIT) -> list[Listing]:
    try:
        client = await get_client()
        feed = await client.get_feed()
    except Exception as e:
        print(f"[mrkt] fetch error: {e}")
        return []

    listings = []
    for item in (feed.items or []):
        if item.type != "listing":
            continue
        try:
            price = float(item.amount_ton)
            if price < PRICE_MIN or price > PRICE_MAX:
                continue
            listings.append(Listing(
                source=SOURCE,
                item_id=str(item.id),
                name=item.gift.title,
                model=item.gift.model_title,
                price=price,
                url="https://t.me/mrkt/app",
            ))
            if len(listings) >= limit:
                break
        except Exception:
            continue
    return listings

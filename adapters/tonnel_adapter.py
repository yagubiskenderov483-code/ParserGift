import asyncio
from tonnelmp import getGifts
from adapters.base import Listing
from config import PRICE_MIN, PRICE_MAX, FETCH_LIMIT

SOURCE = "Tonnel"

def _fetch_sync(limit: int):
    # sort="latest" — самые свежие выставленные лоты первыми
    return getGifts(
        sort="latest",
        limit=limit,
        asset="TON",
        price_range=[PRICE_MIN, PRICE_MAX],
    )

async def fetch_latest(limit: int = FETCH_LIMIT) -> list[Listing]:
    loop = asyncio.get_running_loop()
    try:
        raw = await loop.run_in_executor(None, _fetch_sync, limit)
    except Exception as e:
        print(f"[tonnel] fetch error: {e}")
        return []

    listings = []
    for g in raw or []:
        try:
            price = float(g.get("price", 0))
            if price < PRICE_MIN or price > PRICE_MAX:
                continue
            listings.append(Listing(
                source=SOURCE,
                item_id=str(g.get("gift_id")),
                name=g.get("name", "?"),
                model=g.get("model"),
                price=price,
                url="https://t.me/tonnel_network_bot/gifts",
            ))
        except Exception:
            continue
    return listings

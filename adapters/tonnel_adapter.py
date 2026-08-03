import asyncio
from tonnelmp import getGifts
from adapters.base import Listing

SOURCE = "Tonnel"

def _fetch_sync(limit: int = 20):
    # sort="latest" -> самые свежие выставленные лоты первыми
    return getGifts(sort="latest", limit=limit, asset="TON")

async def fetch_latest(limit: int = 20) -> list[Listing]:
    loop = asyncio.get_running_loop()
    try:
        raw = await loop.run_in_executor(None, _fetch_sync, limit)
    except Exception as e:
        print(f"[tonnel] fetch error: {e}")
        return []

    listings = []
    for g in raw or []:
        try:
            listings.append(Listing(
                source=SOURCE,
                item_id=str(g.get("gift_id")),
                name=g.get("name", "?"),
                model=g.get("model"),
                price=float(g.get("price", 0)),
                url="https://t.me/tonnel_network_bot/gifts",
            ))
        except Exception:
            continue
    return listings

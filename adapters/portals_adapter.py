import asyncio
from portalsmp import marketActivity
from adapters.base import Listing

SOURCE = "Portals"

def _fetch_sync(limit: int = 20):
    # activityType="listing" -> только новые выставления, не продажи/офферы
    return marketActivity(sort="latest", limit=limit, activityType="listing")

async def fetch_latest(limit: int = 20) -> list[Listing]:
    loop = asyncio.get_running_loop()
    try:
        raw = await loop.run_in_executor(None, _fetch_sync, limit)
    except Exception as e:
        print(f"[portals] fetch error: {e}")
        return []

    listings = []
    for a in raw or []:
        try:
            listings.append(Listing(
                source=SOURCE,
                item_id=str(a.get("nft_id") or a.get("id")),
                name=a.get("name", "?"),
                model=a.get("model"),
                price=float(a.get("amount") or a.get("price", 0)),
                url="https://t.me/portals/market",
            ))
        except Exception:
            continue
    return listings

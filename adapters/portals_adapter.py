import asyncio
from portalsmp import marketActivity
from adapters.base import Listing
from config import load_portals_auth, PRICE_MIN, PRICE_MAX, FETCH_LIMIT

SOURCE = "Portals"

def _fetch_sync(limit: int, auth_data: str):
    return marketActivity(
        sort="latest",
        limit=limit,
        activityType="listing",
        min_price=PRICE_MIN,
        max_price=PRICE_MAX,
        authData=auth_data,
    )

async def fetch_latest(limit: int = FETCH_LIMIT) -> list[Listing]:
    auth_data = load_portals_auth()
    if not auth_data:
        return []  # ещё не привязан аккаунт, ждём /start

    loop = asyncio.get_running_loop()
    try:
        raw = await loop.run_in_executor(None, _fetch_sync, limit, auth_data)
    except Exception as e:
        print(f"[portals] fetch error: {e}")
        return []

    listings = []
    for a in raw or []:
        try:
            price = float(a.get("amount") or a.get("price") or 0)
            if price < PRICE_MIN or price > PRICE_MAX:
                continue
            name = a.get("name") or (a.get("nft") or {}).get("name") or "?"
            model = a.get("model")
            if model is None and isinstance(a.get("nft"), dict):
                attrs = a["nft"].get("attributes") or []
                for attr in attrs:
                    if attr.get("type") == "model":
                        model = attr.get("value")
                        break
            listings.append(Listing(
                source=SOURCE,
                item_id=str(a.get("nft_id") or a.get("id")),
                name=name,
                model=model,
                price=price,
                url="https://t.me/portals/market",
            ))
        except Exception:
            continue
    return listings

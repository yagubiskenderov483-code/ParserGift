import asyncio

from portalsmp import marketActivity

from adapters.base import Listing
from config import FETCH_LIMIT, PRICE_MAX, PRICE_MIN, load_portals_auth

SOURCE = "Portals"
URL = "https://t.me/portals/market"


def _sync_fetch(limit: int, auth: str):
    return marketActivity(
        sort="latest",
        limit=limit,
        activityType="listing",
        min_price=PRICE_MIN,
        max_price=PRICE_MAX,
        authData=auth,
    )


def _model_from(item: dict) -> str | None:
    if item.get("model"):
        return item["model"]
    nft = item.get("nft")
    if isinstance(nft, dict):
        for attr in nft.get("attributes") or []:
            if attr.get("type") == "model":
                return attr.get("value")
    return None


async def fetch_latest(limit: int = FETCH_LIMIT) -> list[Listing]:
    auth = load_portals_auth()
    if not auth:
        return []

    loop = asyncio.get_running_loop()
    try:
        raw = await loop.run_in_executor(None, _sync_fetch, limit, auth)
    except Exception as e:
        print(f"[portals] {e}")
        return []

    out: list[Listing] = []
    for a in raw or []:
        try:
            price = float(a.get("amount") or a.get("price") or 0)
            if price < PRICE_MIN or price > PRICE_MAX:
                continue
            name = a.get("name") or (a.get("nft") or {}).get("name") or "?"
            out.append(
                Listing(
                    source=SOURCE,
                    item_id=str(a.get("nft_id") or a.get("id")),
                    name=name,
                    model=_model_from(a),
                    price=price,
                    url=URL,
                )
            )
        except Exception:
            continue
    return out

import asyncio

from tonnelmp import getGifts

from adapters.base import Listing
from config import FETCH_LIMIT, PRICE_MAX, PRICE_MIN

SOURCE = "Tonnel"
URL = "https://t.me/tonnel_network_bot/gifts"


def _sync_fetch(limit: int):
    return getGifts(
        sort="latest",
        limit=limit,
        asset="TON",
        price_range=[PRICE_MIN, PRICE_MAX],
    )


async def fetch_latest(limit: int = FETCH_LIMIT) -> list[Listing]:
    loop = asyncio.get_running_loop()
    try:
        raw = await loop.run_in_executor(None, _sync_fetch, limit)
    except Exception as e:
        print(f"[tonnel] {e}")
        return []

    out: list[Listing] = []
    for g in raw or []:
        try:
            price = float(g.get("price", 0))
            if price < PRICE_MIN or price > PRICE_MAX:
                continue
            out.append(
                Listing(
                    source=SOURCE,
                    item_id=str(g.get("gift_id")),
                    name=g.get("name", "?"),
                    model=g.get("model"),
                    price=price,
                    url=URL,
                )
            )
        except Exception:
            continue
    return out

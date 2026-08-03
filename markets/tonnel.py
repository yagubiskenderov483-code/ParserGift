from __future__ import annotations

import asyncio

from tonnelmp import getGifts

from config import LIMIT, PRICE_MAX, PRICE_MIN
from db import Lot

LINK = "https://t.me/tonnel_network_bot/gifts"


def _pull(limit: int):
    return getGifts(
        sort="latest",
        limit=limit,
        asset="TON",
        price_range=[PRICE_MIN, PRICE_MAX],
    )


async def latest(limit: int = LIMIT) -> list[Lot]:
    loop = asyncio.get_running_loop()
    try:
        raw = await loop.run_in_executor(None, _pull, limit)
    except Exception as e:
        print(f"[tonnel] {e}")
        return []

    lots: list[Lot] = []
    for g in raw or []:
        try:
            price = float(g.get("price") or 0)
            if price < PRICE_MIN or price > PRICE_MAX:
                continue
            gid = g.get("gift_id")
            if gid is None:
                continue
            lots.append(
                Lot(
                    market="Tonnel",
                    lot_id=f"tonnel:{gid}",
                    title=str(g.get("name") or "?"),
                    model=g.get("model"),
                    price=price,
                    link=LINK,
                )
            )
        except Exception:
            continue
    return lots

"""Tonnel — свежие лоты (sort=latest), фильтр 2k–60k TON."""

from __future__ import annotations

import asyncio

from tonnelmp import getGifts

from config import LIMIT, PRICE_MAX, PRICE_MIN

URL = "https://t.me/tonnel_network_bot/gifts"


def _fetch(limit: int):
    return getGifts(
        sort="latest",
        limit=limit,
        asset="TON",
        price_range=[PRICE_MIN, PRICE_MAX],
    )


async def fetch_new(limit: int = LIMIT) -> list[dict]:
    loop = asyncio.get_running_loop()
    try:
        raw = await loop.run_in_executor(None, _fetch, limit)
    except Exception as e:
        print(f"[tonnel] {e}")
        return []

    out = []
    for g in raw or []:
        try:
            price = float(g.get("price") or 0)
            if not (PRICE_MIN <= price <= PRICE_MAX):
                continue
            gid = g.get("gift_id")
            if gid is None:
                continue
            out.append(
                {
                    "id": f"tonnel:{gid}",
                    "market": "Tonnel",
                    "title": str(g.get("name") or "?"),
                    "model": g.get("model"),
                    "price": price,
                    "url": URL,
                }
            )
        except Exception:
            continue
    return out

from __future__ import annotations

import os
import shutil

from amrkt import MarketClient

from config import API_HASH, API_ID, LIMIT, MRKT_SESSION, PRICE_MAX, PRICE_MIN, SESSION
from db import Lot

LINK = "https://t.me/mrkt/app"

_client: MarketClient | None = None


def _copy_session() -> None:
    src, dst = f"{SESSION}.session", f"{MRKT_SESSION}.session"
    if os.path.exists(src) and not os.path.exists(dst):
        try:
            shutil.copy2(src, dst)
        except Exception as e:
            print(f"[mrkt] copy session: {e}")


async def _get() -> MarketClient:
    global _client
    if _client is None:
        _copy_session()
        _client = MarketClient(
            api_id=API_ID,
            api_hash=API_HASH,
            session_name=MRKT_SESSION,
        )
        await _client.__aenter__()
    return _client


async def latest(limit: int = LIMIT) -> list[Lot]:
    try:
        client = await _get()
        feed = await client.get_feed()
    except Exception as e:
        print(f"[mrkt] {e}")
        return []

    lots: list[Lot] = []
    for item in feed.items or []:
        if getattr(item, "type", None) != "listing":
            continue
        try:
            price = float(item.amount_ton)
            if price < PRICE_MIN or price > PRICE_MAX:
                continue
            lots.append(
                Lot(
                    market="MRKT",
                    lot_id=f"mrkt:{item.id}",
                    title=item.gift.title,
                    model=getattr(item.gift, "model_title", None),
                    price=price,
                    link=LINK,
                )
            )
            if len(lots) >= limit:
                break
        except Exception:
            continue
    return lots

from __future__ import annotations

import asyncio

from portalsmp import marketActivity

from config import LIMIT, PRICE_MAX, PRICE_MIN
from db import Lot, load_json

LINK = "https://t.me/portals/market"
AUTH_PATH = "portals_auth.json"


def _model(item: dict) -> str | None:
    if item.get("model"):
        return str(item["model"])
    nft = item.get("nft")
    if isinstance(nft, dict):
        for a in nft.get("attributes") or []:
            if a.get("type") == "model":
                return a.get("value")
    return None


def _pull(limit: int, auth: str):
    return marketActivity(
        sort="latest",
        limit=limit,
        activityType="listing",
        min_price=int(PRICE_MIN),
        max_price=int(PRICE_MAX),
        authData=auth,
    )


async def latest(limit: int = LIMIT) -> list[Lot]:
    auth = load_json(AUTH_PATH, "authData")
    if not auth:
        return []

    loop = asyncio.get_running_loop()
    try:
        raw = await loop.run_in_executor(None, _pull, limit, auth)
    except Exception as e:
        print(f"[portals] {e}")
        return []

    lots: list[Lot] = []
    for a in raw or []:
        try:
            price = float(a.get("amount") or a.get("price") or 0)
            if price < PRICE_MIN or price > PRICE_MAX:
                continue
            nid = a.get("nft_id") or a.get("id")
            if not nid:
                continue
            name = a.get("name")
            if not name and isinstance(a.get("nft"), dict):
                name = a["nft"].get("name")
            lots.append(
                Lot(
                    market="Portals",
                    lot_id=f"portals:{nid}",
                    title=str(name or "?"),
                    model=_model(a),
                    price=price,
                    link=LINK,
                )
            )
        except Exception:
            continue
    return lots

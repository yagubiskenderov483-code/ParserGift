"""Portals — новые listing через marketActivity(sort=latest)."""

from __future__ import annotations

import asyncio
import json
import os

from portalsmp import marketActivity

from config import LIMIT, PRICE_MAX, PRICE_MIN

URL = "https://t.me/portals/market"
AUTH_FILE = "portals_auth.json"


def load_auth() -> str | None:
    if not os.path.exists(AUTH_FILE):
        return None
    try:
        with open(AUTH_FILE, encoding="utf-8") as f:
            return json.load(f).get("authData")
    except Exception:
        return None


def save_auth(auth: str) -> None:
    with open(AUTH_FILE, "w", encoding="utf-8") as f:
        json.dump({"authData": auth}, f)


def _model(item: dict) -> str | None:
    if item.get("model"):
        return str(item["model"])
    nft = item.get("nft")
    if isinstance(nft, dict):
        for a in nft.get("attributes") or []:
            if a.get("type") == "model":
                return a.get("value")
    return None


def _fetch(limit: int, auth: str):
    return marketActivity(
        sort="latest",
        limit=limit,
        activityType="listing",
        min_price=int(PRICE_MIN),
        max_price=int(PRICE_MAX),
        authData=auth,
    )


async def fetch_new(limit: int = LIMIT) -> list[dict]:
    auth = load_auth()
    if not auth:
        return []

    loop = asyncio.get_running_loop()
    try:
        raw = await loop.run_in_executor(None, _fetch, limit, auth)
    except Exception as e:
        print(f"[portals] {e}")
        return []

    out = []
    for a in raw or []:
        try:
            price = float(a.get("amount") or a.get("price") or 0)
            if not (PRICE_MIN <= price <= PRICE_MAX):
                continue
            nid = a.get("nft_id") or a.get("id")
            if not nid:
                continue
            title = a.get("name")
            if not title and isinstance(a.get("nft"), dict):
                title = a["nft"].get("name")
            out.append(
                {
                    "id": f"portals:{nid}",
                    "market": "Portals",
                    "title": str(title or "?"),
                    "model": _model(a),
                    "price": price,
                    "url": URL,
                }
            )
        except Exception:
            continue
    return out

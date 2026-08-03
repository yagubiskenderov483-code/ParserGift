"""MRKT — лента get_feed(), только type=listing, 2k–60k TON."""

from __future__ import annotations

import os
import shutil

from amrkt import MarketClient

from config import API_HASH, API_ID, LIMIT, MRKT_SESSION, PRICE_MAX, PRICE_MIN, SESSION

URL = "https://t.me/mrkt/app"

_client: MarketClient | None = None


def ensure_session() -> None:
    src, dst = f"{SESSION}.session", f"{MRKT_SESSION}.session"
    if os.path.exists(src) and not os.path.exists(dst):
        try:
            shutil.copy2(src, dst)
        except Exception as e:
            print(f"[mrkt] session: {e}")


async def _client_get() -> MarketClient:
    global _client
    if _client is None:
        ensure_session()
        _client = MarketClient(
            api_id=API_ID,
            api_hash=API_HASH,
            session_name=MRKT_SESSION,
        )
        await _client.__aenter__()
    return _client


async def fetch_new(limit: int = LIMIT) -> list[dict]:
    try:
        client = await _client_get()
        feed = await client.get_feed()
    except Exception as e:
        print(f"[mrkt] {e}")
        return []

    out = []
    for item in feed.items or []:
        if getattr(item, "type", None) != "listing":
            continue
        try:
            price = float(item.amount_ton)
            if not (PRICE_MIN <= price <= PRICE_MAX):
                continue
            out.append(
                {
                    "id": f"mrkt:{item.id}",
                    "market": "MRKT",
                    "title": item.gift.title,
                    "model": getattr(item.gift, "model_title", None),
                    "price": price,
                    "url": URL,
                }
            )
            if len(out) >= limit:
                break
        except Exception:
            continue
    return out

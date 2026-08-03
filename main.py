from amrkt import MarketClient
from adapters.base import Listing
from config import API_ID, API_HASH

SOURCE = "MRKT"

_client: MarketClient | None = None

async def get_client() -> MarketClient:
    global _client
    if _client is None:
        _client = MarketClient(
            api_id=API_ID,
            api_hash=API_HASH,
            session_name="mrkt_session",   # при первом запуске попросит войти в Telegram (номер/код)
        )
        await _client.__aenter__()
    return _client

async def fetch_latest(limit: int = 20) -> list[Listing]:
    try:
        client = await get_client()
        feed = await client.get_feed()
    except Exception as e:
        print(f"[mrkt] fetch error: {e}")
        return []

    listings = []
    for item in (feed.items or [])[:limit]:
        if item.type != "listing":
            continue
        try:
            listings.append(Listing(
                source=SOURCE,
                item_id=str(item.id),
                name=item.gift.title,
                model=item.gift.model_title,
                price=float(item.amount_ton),
                url="https://t.me/mrkt/app",
            ))
        except Exception:
            continue
    return listings

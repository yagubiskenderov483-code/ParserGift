from dataclasses import dataclass


@dataclass
class Listing:
    source: str
    item_id: str
    name: str
    model: str | None
    price: float
    url: str | None = None

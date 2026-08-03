from dataclasses import dataclass

@dataclass
class Listing:
    source: str          # "Tonnel" / "Portals" / "MRKT"
    item_id: str          # уникальный id лота на площадке
    name: str              # название подарка
    model: str | None      # модель/редкость
    price: float           # цена (в TON)
    url: str | None = None

from __future__ import annotations

import json
import os
from dataclasses import dataclass


@dataclass
class Lot:
    market: str
    lot_id: str
    title: str
    model: str | None
    price: float
    link: str


class Seen:
    def __init__(self, path: str = "seen.json", limit: int = 5000):
        self.path = path
        self.limit = limit
        self.data: dict[str, list[str]] = {}
        self.idx: dict[str, set[str]] = {}
        if os.path.exists(path):
            try:
                with open(path, encoding="utf-8") as f:
                    self.data = json.load(f)
            except Exception:
                self.data = {}
        for k, v in self.data.items():
            self.idx[k] = set(v)

    def known(self, market: str) -> bool:
        return bool(self.data.get(market))

    def is_new(self, market: str, lot_id: str) -> bool:
        return lot_id not in self.idx.setdefault(market, set())

    def add(self, market: str, ids: list[str]) -> None:
        arr = self.data.setdefault(market, [])
        s = self.idx.setdefault(market, set())
        changed = False
        for i in ids:
            if i in s:
                continue
            arr.append(i)
            s.add(i)
            changed = True
        if len(arr) > self.limit:
            drop = arr[: -self.limit]
            self.data[market] = arr[-self.limit :]
            for d in drop:
                s.discard(d)
            changed = True
        if changed:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self.data, f)


def load_json(path: str, key: str):
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f).get(key)
    except Exception:
        return None


def save_json(path: str, key: str, value) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump({key: value}, f)

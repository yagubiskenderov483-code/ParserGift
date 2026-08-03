import json
import os

from config import SEEN_PATH


class SeenStore:
    MAX = 5000

    def __init__(self, path: str = SEEN_PATH):
        self.path = path
        self.data: dict[str, list[str]] = {}
        self.index: dict[str, set[str]] = {}
        self._load()

    def _load(self) -> None:
        if os.path.exists(self.path):
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    self.data = json.load(f)
            except Exception:
                self.data = {}
        for src, ids in self.data.items():
            self.index[src] = set(ids)

    def _save(self) -> None:
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self.data, f)
        except Exception as e:
            print(f"[storage] {e}")

    def has_history(self, source: str) -> bool:
        return bool(self.data.get(source))

    def is_new(self, source: str, item_id: str) -> bool:
        return item_id not in self.index.setdefault(source, set())

    def mark_many(self, source: str, item_ids: list[str]) -> None:
        ids = self.data.setdefault(source, [])
        idx = self.index.setdefault(source, set())
        changed = False
        for item_id in item_ids:
            if item_id in idx:
                continue
            ids.append(item_id)
            idx.add(item_id)
            changed = True
        if len(ids) > self.MAX:
            dropped = ids[:-self.MAX]
            self.data[source] = ids[-self.MAX:]
            for old in dropped:
                idx.discard(old)
            changed = True
        if changed:
            self._save()

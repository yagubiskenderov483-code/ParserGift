import json
import os
from config import SEEN_STORE_PATH

class SeenStore:
    """Id уже отправленных лотов по каждому маркету — без дублей.
    Размер ограничен, файл не растёт бесконечно."""

    MAX_PER_SOURCE = 5000

    def __init__(self, path: str = SEEN_STORE_PATH):
        self.path = path
        self.data: dict[str, list[str]] = {}
        self._index: dict[str, set[str]] = {}
        self._load()

    def _load(self):
        if os.path.exists(self.path):
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    self.data = json.load(f)
            except Exception:
                self.data = {}
        for source, ids in self.data.items():
            self._index[source] = set(ids)

    def _save(self):
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self.data, f)
        except Exception as e:
            print(f"[storage] save error: {e}")

    def has_history(self, source: str) -> bool:
        return bool(self.data.get(source))

    def is_new(self, source: str, item_id: str) -> bool:
        return item_id not in self._index.setdefault(source, set())

    def mark_seen(self, source: str, item_id: str, *, persist: bool = True):
        ids = self.data.setdefault(source, [])
        idx = self._index.setdefault(source, set())
        if item_id in idx:
            return
        ids.append(item_id)
        idx.add(item_id)
        if len(ids) > self.MAX_PER_SOURCE:
            dropped = ids[:-self.MAX_PER_SOURCE]
            self.data[source] = ids[-self.MAX_PER_SOURCE:]
            for old in dropped:
                idx.discard(old)
        if persist:
            self._save()

    def mark_seen_many(self, source: str, item_ids: list[str]):
        for item_id in item_ids:
            self.mark_seen(source, item_id, persist=False)
        self._save()

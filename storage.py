import json
import os
from config import SEEN_STORE_PATH

class SeenStore:
    """Держит id уже отправленных лотов по каждому маркету, чтобы не спамить дублями.
    Ограничиваем размер, чтобы файл не рос бесконечно."""

    MAX_PER_SOURCE = 5000

    def __init__(self, path: str = SEEN_STORE_PATH):
        self.path = path
        self.data: dict[str, list[str]] = {}
        self._load()

    def _load(self):
        if os.path.exists(self.path):
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    self.data = json.load(f)
            except Exception:
                self.data = {}

    def _save(self):
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self.data, f)
        except Exception as e:
            print(f"[storage] save error: {e}")

    def is_new(self, source: str, item_id: str) -> bool:
        ids = self.data.setdefault(source, [])
        return item_id not in ids

    def mark_seen(self, source: str, item_id: str):
        ids = self.data.setdefault(source, [])
        ids.append(item_id)
        if len(ids) > self.MAX_PER_SOURCE:
            self.data[source] = ids[-self.MAX_PER_SOURCE:]
        self._save()

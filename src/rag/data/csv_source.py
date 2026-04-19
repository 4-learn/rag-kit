"""CSV DataSource

從本地 CSV 檔讀取。適合離線測試或把 Google Sheet 同步下來當 cache。
"""

import csv
from pathlib import Path


class CSVDataSource:
    """從本地 CSV 檔讀取。

    Args:
        path: CSV 檔路徑
        key_column: 作為主鍵的欄位名稱（預設是第一個欄位）
    """

    def __init__(self, path: str | Path, key_column: str | None = None):
        self.path = Path(path)
        self.key_column = key_column
        self._cache: list[dict] | None = None

    def _load(self) -> list[dict]:
        if self._cache is not None:
            return self._cache

        with open(self.path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = [dict(r) for r in reader]

        if self.key_column is None and rows:
            self.key_column = next(iter(rows[0].keys()))

        self._cache = rows
        return rows

    def all_rows(self) -> list[dict]:
        return list(self._load())

    def by_key(self, key: str) -> dict | None:
        for row in self._load():
            if (row.get(self.key_column) or "").strip() == key:
                return row
        return None

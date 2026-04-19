"""Google Sheet DataSource

從公開的 Google Sheet CSV export URL 讀取資料。
需要 sheet 設為「擁有連結者皆可檢視」。
"""

import csv
import io

import requests


class GoogleSheetDataSource:
    """從 Google Sheet 的 CSV export URL 讀取。

    Args:
        csv_url: Google Sheet 的 CSV export URL
                 (格式: https://docs.google.com/spreadsheets/d/{id}/export?format=csv)
        key_column: 作為主鍵的欄位名稱（預設是第一個欄位）
    """

    def __init__(self, csv_url: str, key_column: str | None = None):
        self.csv_url = csv_url
        self.key_column = key_column
        self._cache: list[dict] | None = None

    def _load(self) -> list[dict]:
        if self._cache is not None:
            return self._cache

        resp = requests.get(self.csv_url)
        resp.encoding = "utf-8"
        reader = csv.DictReader(io.StringIO(resp.text))
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

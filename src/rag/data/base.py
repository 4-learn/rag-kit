"""DataSource Protocol

所有資料來源（Google Sheet、CSV、DB 等）都實作這個介面，
讓上層 (Retriever / Generator) 不需要關心資料從哪裡來。
"""

from typing import Protocol


class DataSource(Protocol):
    """資料來源介面。

    實作者只要提供兩個方法：
      - all_rows(): 回傳所有列（dict list，欄名對應 sheet 欄位）
      - by_key(key): 用主鍵拿單一列
    """

    def all_rows(self) -> list[dict]:
        ...

    def by_key(self, key: str) -> dict | None:
        ...

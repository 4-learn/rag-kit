"""Retriever Protocol

Retriever 的責任：給一個 query（文字或圖片），回傳候選的 key list。
"""

from typing import Any, Protocol


class Retriever(Protocol):
    """檢索層介面。

    retrieve(query) 回傳的是「key list」，不是整列資料。
    拿到 key 之後，Pipeline 會用 DataSource.by_key() 補上完整資料。
    這樣可以讓不同 Retriever 實作（向量、BM25、all-in-prompt）回傳統一格式。
    """

    def retrieve(self, query: Any) -> list[str]:
        ...

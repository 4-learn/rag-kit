"""Generator Protocol

Generator 的責任：把 Retriever 撈到的 payload + 原始 query，生成最終回答。
"""

from typing import Any, Protocol


class Generator(Protocol):
    """生成層介面。

    Args:
        payload: Pipeline 組好的 context（通常是 dict，裡面有候選列、原始資料等）
        query:   使用者的原始 query（文字、圖片 bytes、或 multimodal dict）

    Returns:
        最終回答的字串（可以是 JSON、markdown、純文字——由實作決定）
    """

    def generate(self, payload: dict, query: Any) -> str:
        ...

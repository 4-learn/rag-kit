"""RAG Pipeline

把 DataSource / Retriever / Generator 三層組起來。

流程：
    query
      │
      ▼
    Retriever.retrieve(query)   → list[key]
      │
      ▼
    DataSource.by_key(key) × N  → payload
      │
      ▼
    Generator.generate(payload, query) → 回答
"""

from typing import Any

from .data.base import DataSource
from .generator.base import Generator
from .retriever.base import Retriever


class RAGPipeline:
    """四層架構的組裝器。

    Args:
        data_source:  用來把 key 還原成完整列
        retriever:    負責從 query 產出候選 key list
        generator:    拿 payload + query 生成最終回答
    """

    def __init__(
        self,
        data_source: DataSource,
        retriever: Retriever,
        generator: Generator,
    ):
        self.data_source = data_source
        self.retriever = retriever
        self.generator = generator

    def run(self, query: Any) -> str:
        """跑完整 RAG 流程。"""
        keys = self.retriever.retrieve(query)
        rows = [r for k in keys if (r := self.data_source.by_key(k)) is not None]
        payload = {"rows": rows, "keys": keys}
        return self.generator.generate(payload, query)

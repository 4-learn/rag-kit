"""rag-kit — 4 層 RAG 骨架

Layers:
    data        — DataSource Protocol (原始資料層)
    retriever   — Retriever Protocol (檢索層)
    generator   — Generator Protocol (生成層)
    pipeline    — RAGPipeline (組裝三層)
"""

from .pipeline import RAGPipeline

__all__ = ["RAGPipeline"]

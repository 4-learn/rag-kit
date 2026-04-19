"""Retriever 測試 — AllInPromptRetriever 的行為驗證。"""

from pathlib import Path

import pytest

from apps.huwei_landmarks import schema
from src.rag.data import CSVDataSource
from src.rag.retriever import AllInPromptRetriever


FIXTURE = Path(__file__).parent / "fixtures" / "landmarks_mini.csv"


def test_retriever_returns_all_valid_keys():
    ds = CSVDataSource(FIXTURE, key_column=schema.KEY_COLUMN)
    retriever = AllInPromptRetriever(ds, key_field=schema.KEY_COLUMN)
    keys = retriever.retrieve(query=None)
    assert "雲林布袋戲館" in keys
    assert all(isinstance(k, str) for k in keys)


def test_retriever_dedupes_keys():
    ds = CSVDataSource(FIXTURE, key_column=schema.KEY_COLUMN)
    retriever = AllInPromptRetriever(ds, key_field=schema.KEY_COLUMN)
    keys = retriever.retrieve(query=None)
    assert len(keys) == len(set(keys))


def test_retriever_filter_fn_drops_invalid_rows():
    ds = CSVDataSource(FIXTURE, key_column=schema.KEY_COLUMN)
    retriever = AllInPromptRetriever(
        ds,
        key_field=schema.KEY_COLUMN,
        filter_fn=schema.row_is_valid,
    )
    keys = retriever.retrieve(query=None)
    # 空白列在 fixture 中存在，filter 應濾掉
    assert "" not in keys


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

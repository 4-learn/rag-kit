"""Data layer 測試 — 用本地 CSV 確認 DataSource 介面行為正確。"""

from pathlib import Path

import pytest

from src.rag.data import CSVDataSource


FIXTURE = Path(__file__).parent / "fixtures" / "landmarks_mini.csv"


def test_csv_all_rows_returns_list_of_dicts():
    ds = CSVDataSource(FIXTURE, key_column="地點名稱 (name)")
    rows = ds.all_rows()
    assert isinstance(rows, list)
    assert all(isinstance(r, dict) for r in rows)
    assert len(rows) >= 1


def test_csv_by_key_returns_matching_row():
    ds = CSVDataSource(FIXTURE, key_column="地點名稱 (name)")
    row = ds.by_key("雲林布袋戲館")
    assert row is not None
    assert row["地點名稱 (name)"] == "雲林布袋戲館"


def test_csv_by_key_returns_none_for_missing():
    ds = CSVDataSource(FIXTURE, key_column="地點名稱 (name)")
    assert ds.by_key("不存在的地點") is None


def test_csv_all_rows_returns_fresh_list_each_call():
    """呼叫方改動回傳 list 不應影響下一次結果。"""
    ds = CSVDataSource(FIXTURE, key_column="地點名稱 (name)")
    first = ds.all_rows()
    first.clear()
    second = ds.all_rows()
    assert len(second) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

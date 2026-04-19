"""虎尾地標 Sheet 的欄位定義

集中管理 sheet 欄位名稱。之後若 sheet 欄位改名，只動這一支。
"""

# Google Sheet 原始欄位名（含中英對照，不要動——對應到真實 sheet header）
COL_NAME = "地點名稱 (name)"
COL_STYLE = "建築風格 (style)"
COL_STRUCT = "建築結構 (struct)"
COL_MATERIAL = "材質 (material)"
COL_FUNCTION = "功能用途 (function)"
COL_SUMMARY = "簡介 (summary)"

# 主鍵欄位
KEY_COLUMN = COL_NAME

# 所有供 Retriever/Generator 用的特徵欄位
FEATURE_COLUMNS = [
    ("style", COL_STYLE, "風格"),
    ("struct", COL_STRUCT, "結構"),
    ("material", COL_MATERIAL, "材質"),
    ("function", COL_FUNCTION, "用途"),
    ("summary", COL_SUMMARY, "簡介"),
]

# summary 截斷長度（避免 prompt 過長）
SUMMARY_MAX_LEN = 120


def row_is_valid(row: dict) -> bool:
    """判斷一列是否有效（地點名稱非空）"""
    return bool((row.get(KEY_COLUMN) or "").strip())

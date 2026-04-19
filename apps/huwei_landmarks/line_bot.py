"""LINE BOT presentation layer — pipeline glue.

把 RAGPipeline 包成「吃 bytes → 吐人話」的介面，供 `server.py` 的
webhook handler 呼叫。本檔刻意不 import 任何 LINE SDK — 保持 pipeline
glue 與 webhook 分離，方便單元測試。

執行方式：由 `apps.huwei_landmarks.server` 啟動 FastAPI 後，LINE
webhook 會進來呼叫 `handle_image_message()`。
"""

from __future__ import annotations

import json
import os
from typing import Optional

import requests
from dotenv import load_dotenv

from .config import DEFAULT_SHEET_CSV_URL, build_pipeline

load_dotenv()

# 模組層 pipeline cache — 避免每則訊息都重建（會重新抓 Sheet）。
_pipeline_cache = None


def _resolve_api_key(explicit: Optional[str] = None) -> str:
    """取得 Gemini API key。GEMINI_API_KEY 優先、GOOGLE_API_KEY 次之。"""
    key = explicit or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not key:
        raise RuntimeError(
            "缺少 GEMINI_API_KEY / GOOGLE_API_KEY 環境變數，無法呼叫 Gemini"
        )
    return key


def _resolve_sheet_url() -> str:
    return os.environ.get("LANDMARKS_SHEET_CSV_URL") or DEFAULT_SHEET_CSV_URL


def get_pipeline(rebuild: bool = False):
    """回傳共用的 RAGPipeline（惰性建立 + 快取）。

    Args:
        rebuild: 強制重建（例如 Sheet 有更新時）
    """
    global _pipeline_cache
    if _pipeline_cache is not None and not rebuild:
        return _pipeline_cache

    api_key = _resolve_api_key()

    # 若設了自訂 Sheet URL，用 env 值；否則走 config.py 的 default
    sheet_url = _resolve_sheet_url()
    if sheet_url != DEFAULT_SHEET_CSV_URL:
        # 只在覆寫時才動 GoogleSheetDataSource — 沿用 config.build_pipeline
        # 但資料源換一下。這裡為了 KISS 做 monkey-patch 等級的替換：
        from src.rag.data import GoogleSheetDataSource
        from src.rag.retriever import AllInPromptRetriever
        from src.rag.generator import GeminiGenerator
        from src.rag import RAGPipeline

        from . import schema
        from .config import build_prompt

        data_source = GoogleSheetDataSource(sheet_url, key_column=schema.KEY_COLUMN)
        retriever = AllInPromptRetriever(
            data_source=data_source,
            key_field=schema.KEY_COLUMN,
            filter_fn=schema.row_is_valid,
        )
        generator = GeminiGenerator(api_key=api_key, prompt_builder=build_prompt)
        _pipeline_cache = RAGPipeline(
            data_source=data_source,
            retriever=retriever,
            generator=generator,
        )
    else:
        _pipeline_cache = build_pipeline(api_key=api_key)
    return _pipeline_cache


def handle_image_message(image_bytes: bytes) -> str:
    """收到使用者傳來的照片 → 回傳地標辨識結果文字。

    這個函式就是 LINE webhook handler 要呼叫的核心——把 RAG pipeline
    包成「吃 bytes，吐人話」的簡單介面。
    """
    pipeline = get_pipeline()

    raw = pipeline.run({"image_bytes": image_bytes, "mime_type": "image/jpeg"})
    try:
        result = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return f"辨識失敗：{str(raw)[:100]}"

    if not isinstance(result, dict):
        return f"辨識失敗：非預期的回傳格式 {str(result)[:100]}"

    if "error" in result:
        return f"辨識失敗：{result['error']}"

    name = result.get("name", "未知地點")
    reason = result.get("reason", "")
    confidence = result.get("confidence", "")
    return f"地點：{name}\n依據：{reason}\n信心：{confidence}"


def download_line_image(message_id: str, channel_token: str) -> bytes:
    """從 LINE Messaging API 下載使用者上傳的圖片（HTTP fallback）。

    `server.py` 正常流程走 SDK 的 MessagingApiBlob；這個函式保留
    給需要純 HTTP 測試 / debug 的情境使用。
    """
    url = f"https://api-data.line.me/v2/bot/message/{message_id}/content"
    resp = requests.get(url, headers={"Authorization": f"Bearer {channel_token}"})
    resp.raise_for_status()
    return resp.content


def main():  # pragma: no cover
    print("LINE BOT handler 骨架就緒。")
    print("啟動 webhook：uvicorn apps.huwei_landmarks.server:app --reload")


if __name__ == "__main__":  # pragma: no cover
    main()

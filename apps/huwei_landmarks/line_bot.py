"""LINE BOT presentation layer（骨架）

目前 repo 內尚無 LINE BOT 既有實作，本檔提供最小骨架，示範如何把
RAGPipeline 接到 LINE webhook 上。實際 webhook 路由與簽章驗證由
課程後續 issue 完成。

執行方式（待實作完 webhook 後）：
    python -m apps.huwei_landmarks.line_bot
"""

import json
import os

import requests
from dotenv import load_dotenv

from .config import build_pipeline

load_dotenv()


def handle_image_message(image_bytes: bytes) -> str:
    """收到使用者傳來的照片 → 回傳地標辨識結果文字。

    這個函式就是 LINE webhook handler 要呼叫的核心——把 RAG pipeline
    包成「吃 bytes，吐人話」的簡單介面。
    """
    api_key = os.getenv("GOOGLE_API_KEY")
    pipeline = build_pipeline(api_key=api_key)

    raw = pipeline.run({"image_bytes": image_bytes, "mime_type": "image/png"})
    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        return f"辨識失敗：{raw[:100]}"

    if "error" in result:
        return f"辨識失敗：{result['error']}"

    name = result.get("name", "未知地點")
    reason = result.get("reason", "")
    confidence = result.get("confidence", "")
    return f"地點：{name}\n依據：{reason}\n信心：{confidence}"


def download_line_image(message_id: str, channel_token: str) -> bytes:
    """從 LINE Messaging API 下載使用者上傳的圖片"""
    url = f"https://api-data.line.me/v2/bot/message/{message_id}/content"
    resp = requests.get(url, headers={"Authorization": f"Bearer {channel_token}"})
    resp.raise_for_status()
    return resp.content


def main():
    print("LINE BOT handler 骨架就緒。")
    print("把 webhook 接進來後，呼叫 handle_image_message(image_bytes) 即可。")


if __name__ == "__main__":
    main()

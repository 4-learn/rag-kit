"""Gemini Generator

呼叫 Google Gemini API 生成回答。支援 multimodal (text + image)。

從原本的 detect.detect_landmark() 拆出來，讓 Generator 不再綁死地標領域：
- prompt template 由 app 層（huwei_landmarks）提供
- 欄位組裝也由 app 層決定
"""

import base64
import json
from typing import Any, Callable

import requests


class GeminiGenerator:
    """用 Gemini API 做生成。

    Args:
        api_key: Google API Key
        model:   Gemini 模型名稱（預設 gemini-2.5-flash）
        prompt_builder: callable(payload, query) -> str，組出 prompt 文字
        response_mime_type: 預設 "application/json"
    """

    API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"

    def __init__(
        self,
        api_key: str,
        prompt_builder: Callable[[dict, Any], str],
        model: str = "gemini-2.5-flash",
        response_mime_type: str = "application/json",
    ):
        self.api_key = api_key
        self.model = model
        self.prompt_builder = prompt_builder
        self.response_mime_type = response_mime_type

    def generate(self, payload: dict, query: Any) -> str:
        prompt_text = self.prompt_builder(payload, query)

        parts: list[dict] = [{"text": prompt_text}]

        # query 支援 {"image_bytes": bytes, "mime_type": "image/png"} 或 str
        if isinstance(query, dict) and "image_bytes" in query:
            img_b64 = base64.b64encode(query["image_bytes"]).decode()
            parts.append({
                "inline_data": {
                    "mime_type": query.get("mime_type", "image/png"),
                    "data": img_b64,
                }
            })

        url = f"{self.API_BASE}/{self.model}:generateContent?key={self.api_key}"
        resp = requests.post(url, json={
            "contents": [{"parts": parts}],
            "generationConfig": {
                "response_mime_type": self.response_mime_type,
            },
        })

        data = resp.json()
        if "error" in data:
            return json.dumps({"error": data["error"]["message"]}, ensure_ascii=False)

        return data["candidates"][0]["content"]["parts"][0]["text"]

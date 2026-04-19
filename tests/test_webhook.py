"""Webhook server 測試 — 驗證 signature、訊息解析、pipeline 呼叫。

這層測試刻意不打 LINE 真的 API / Gemini API：
- pipeline 用 monkey-patch 換成假的
- blob API（下載圖片）用 monkey-patch 換成假的
- signature 用真的 HMAC-SHA256 算出來（= LINE 實際演算法）
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os

import pytest
from fastapi.testclient import TestClient


# ---------- Fixtures ----------

CHANNEL_SECRET = "test-channel-secret"
CHANNEL_TOKEN = "test-channel-access-token"


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    """每支測試都注入固定的 LINE credentials + 假 Gemini key。"""
    monkeypatch.setenv("LINE_CHANNEL_SECRET", CHANNEL_SECRET)
    monkeypatch.setenv("LINE_CHANNEL_ACCESS_TOKEN", CHANNEL_TOKEN)
    monkeypatch.setenv("GEMINI_API_KEY", "fake-gemini-key")
    # 清 pipeline cache — 避免跨測試污染
    from apps.huwei_landmarks import line_bot

    line_bot._pipeline_cache = None
    yield
    line_bot._pipeline_cache = None


@pytest.fixture
def client(monkeypatch):
    """TestClient + 把 pipeline / blob API 替換成假的。"""
    from apps.huwei_landmarks import line_bot, server

    # 假 pipeline — 回傳固定 JSON，避免真的打 Gemini
    class _FakePipeline:
        calls: list = []

        def run(self, query):
            _FakePipeline.calls.append(query)
            return json.dumps(
                {"name": "雲林布袋戲館", "reason": "測試用", "confidence": "high"},
                ensure_ascii=False,
            )

    fake_pipeline = _FakePipeline()
    monkeypatch.setattr(line_bot, "get_pipeline", lambda rebuild=False: fake_pipeline)

    # 假 MessagingApiBlob — 不真的去 LINE 下載
    class _FakeBlobApi:
        downloads: list = []

        def __init__(self, *a, **kw):
            pass

        def get_message_content(self, message_id):
            _FakeBlobApi.downloads.append(message_id)
            return b"\x89PNG\r\n\x1a\nfake-image-bytes"

    # 假 MessagingApi — 錄下 reply 呼叫
    class _FakeMessagingApi:
        replies: list = []

        def __init__(self, *a, **kw):
            pass

        def reply_message(self, req):
            _FakeMessagingApi.replies.append({
                "reply_token": req.reply_token,
                "messages": [m.text for m in req.messages],
            })

    # 假 ApiClient — 做 context manager，其他甚麼都不做
    class _FakeApiClient:
        def __init__(self, *a, **kw):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(server, "ApiClient", _FakeApiClient)
    monkeypatch.setattr(server, "MessagingApi", _FakeMessagingApi)
    monkeypatch.setattr(server, "MessagingApiBlob", _FakeBlobApi)

    tc = TestClient(server.app)
    tc.fake_pipeline = fake_pipeline
    tc.fake_blob = _FakeBlobApi
    tc.fake_messaging = _FakeMessagingApi
    # 重置 class-level counters
    _FakePipeline.calls.clear()
    _FakeBlobApi.downloads.clear()
    _FakeMessagingApi.replies.clear()
    return tc


# ---------- Helpers ----------

def _sign(body: str, secret: str = CHANNEL_SECRET) -> str:
    """LINE 的 webhook signature = Base64(HMAC-SHA256(secret, body))"""
    digest = hmac.new(secret.encode(), body.encode(), hashlib.sha256).digest()
    return base64.b64encode(digest).decode()


def _image_event_body(
    message_id: str = "msg-123",
    reply_token: str = "reply-tok-abc",
    user_id: str = "U-user",
) -> dict:
    return {
        "destination": "U-bot-id",
        "events": [
            {
                "type": "message",
                "timestamp": 1_700_000_000_000,
                "mode": "active",
                "webhookEventId": "01H000000000000000000000",
                "deliveryContext": {"isRedelivery": False},
                "source": {"type": "user", "userId": user_id},
                "replyToken": reply_token,
                "message": {
                    "id": message_id,
                    "type": "image",
                    "quoteToken": "qtok-" + message_id,
                    "contentProvider": {"type": "line"},
                },
            }
        ],
    }


def _text_event_body(text: str = "hi", reply_token: str = "reply-tok-text") -> dict:
    return {
        "destination": "U-bot-id",
        "events": [
            {
                "type": "message",
                "timestamp": 1_700_000_000_000,
                "mode": "active",
                "webhookEventId": "01H000000000000000000001",
                "deliveryContext": {"isRedelivery": False},
                "source": {"type": "user", "userId": "U-user"},
                "replyToken": reply_token,
                "message": {
                    "id": "msg-text",
                    "type": "text",
                    "quoteToken": "qtok-text",
                    "text": text,
                },
            }
        ],
    }


# ---------- Tests ----------

def test_healthz(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.text == "ok"


def test_root_returns_service_info(client):
    r = client.get("/")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"


def test_webhook_rejects_invalid_signature(client):
    body = json.dumps(_image_event_body())
    r = client.post(
        "/webhook",
        content=body,
        headers={"X-Line-Signature": "totally-wrong", "Content-Type": "application/json"},
    )
    assert r.status_code == 400
    assert "signature" in r.json().get("detail", "").lower()


def test_webhook_rejects_missing_signature(client):
    body = json.dumps(_image_event_body())
    r = client.post("/webhook", content=body, headers={"Content-Type": "application/json"})
    assert r.status_code == 400


def test_webhook_accepts_lowercase_signature_header(client):
    """Reverse proxy 有時會把 header 改成全小寫，要能接受。"""
    body = json.dumps(_image_event_body())
    r = client.post(
        "/webhook",
        content=body,
        headers={"x-line-signature": _sign(body), "content-type": "application/json"},
    )
    assert r.status_code == 200


def test_image_event_triggers_pipeline_and_replies(client):
    body = json.dumps(_image_event_body(message_id="m-42", reply_token="rtok-42"))
    r = client.post(
        "/webhook",
        content=body,
        headers={"X-Line-Signature": _sign(body), "Content-Type": "application/json"},
    )
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "events": 1}

    # Blob API 被叫來下載圖片
    assert client.fake_blob.downloads == ["m-42"]

    # Pipeline 被呼叫，query 形狀正確
    assert len(client.fake_pipeline.calls) == 1
    query = client.fake_pipeline.calls[0]
    assert isinstance(query, dict)
    assert "image_bytes" in query
    assert isinstance(query["image_bytes"], (bytes, bytearray))

    # 回覆訊息是 handle_image_message 格式化後的字串
    assert len(client.fake_messaging.replies) == 1
    reply = client.fake_messaging.replies[0]
    assert reply["reply_token"] == "rtok-42"
    assert len(reply["messages"]) == 1
    text = reply["messages"][0]
    assert "雲林布袋戲館" in text
    assert "high" in text


def test_text_event_returns_polite_unsupported_reply(client):
    body = json.dumps(_text_event_body(text="hello", reply_token="rtok-text"))
    r = client.post(
        "/webhook",
        content=body,
        headers={"X-Line-Signature": _sign(body), "Content-Type": "application/json"},
    )
    assert r.status_code == 200

    # Pipeline 不應該被呼叫
    assert client.fake_pipeline.calls == []
    # 應該禮貌回覆一句 "只支援圖片"
    assert len(client.fake_messaging.replies) == 1
    reply = client.fake_messaging.replies[0]
    assert reply["reply_token"] == "rtok-text"
    assert "圖片" in reply["messages"][0]


def test_empty_events_list_returns_ok(client):
    """LINE 有時會送空 events（如驗證 webhook URL），不應炸。"""
    body = json.dumps({"destination": "U-bot", "events": []})
    r = client.post(
        "/webhook",
        content=body,
        headers={"X-Line-Signature": _sign(body), "Content-Type": "application/json"},
    )
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "events": 0}


def test_line_bot_handle_image_message_formats_result(monkeypatch):
    """line_bot.handle_image_message 應把 pipeline 的 JSON 轉成人話。"""
    from apps.huwei_landmarks import line_bot

    class _Fake:
        def run(self, query):
            return json.dumps({
                "name": "虎尾糖廠",
                "reason": "有鐵軌、紅磚煙囪",
                "confidence": "high",
            }, ensure_ascii=False)

    monkeypatch.setattr(line_bot, "get_pipeline", lambda rebuild=False: _Fake())
    out = line_bot.handle_image_message(b"fake-bytes")
    assert "虎尾糖廠" in out
    assert "high" in out


def test_line_bot_handle_image_message_handles_error(monkeypatch):
    from apps.huwei_landmarks import line_bot

    class _Fake:
        def run(self, query):
            return json.dumps({"error": "quota exceeded"}, ensure_ascii=False)

    monkeypatch.setattr(line_bot, "get_pipeline", lambda rebuild=False: _Fake())
    out = line_bot.handle_image_message(b"fake-bytes")
    assert "辨識失敗" in out
    assert "quota exceeded" in out


def test_line_bot_handle_image_message_handles_non_json(monkeypatch):
    from apps.huwei_landmarks import line_bot

    class _Fake:
        def run(self, query):
            return "not-json-at-all"

    monkeypatch.setattr(line_bot, "get_pipeline", lambda rebuild=False: _Fake())
    out = line_bot.handle_image_message(b"fake-bytes")
    assert "辨識失敗" in out


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

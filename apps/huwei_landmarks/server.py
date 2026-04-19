"""LINE BOT webhook server for 虎尾地標辨識

FastAPI app that receives LINE webhook events, verifies the signature,
downloads image messages, runs the RAG pipeline, and replies to the user.

跑法：
    uvicorn apps.huwei_landmarks.server:app --host 0.0.0.0 --port 8000

或透過 docker compose：
    docker compose up

環境變數：
    LINE_CHANNEL_ACCESS_TOKEN  (必要)
    LINE_CHANNEL_SECRET        (必要)
    GEMINI_API_KEY 或 GOOGLE_API_KEY (必要，傳給 pipeline)
    LANDMARKS_SHEET_CSV_URL    (可選，覆寫預設 Sheet URL)
"""

from __future__ import annotations

import logging
import os
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import PlainTextResponse

from linebot.v3 import WebhookParser
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    ApiClient,
    Configuration,
    MessagingApi,
    MessagingApiBlob,
    ReplyMessageRequest,
    TextMessage,
)
from linebot.v3.webhooks import ImageMessageContent, MessageEvent

from . import line_bot

load_dotenv()

logger = logging.getLogger("huwei_landmarks.server")
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))


# ---------- 設定讀取 ----------

def _require_env(name: str) -> str:
    val = os.environ.get(name)
    if not val:
        raise RuntimeError(f"缺少必要環境變數：{name}")
    return val


def _gemini_key() -> str:
    """Pipeline 用的金鑰，GEMINI_API_KEY 優先、退而求其次 GOOGLE_API_KEY。"""
    return (
        os.environ.get("GEMINI_API_KEY")
        or os.environ.get("GOOGLE_API_KEY")
        or ""
    )


UNSUPPORTED_MESSAGE = "目前只支援圖片訊息，請傳一張地標照片給我 📷"


# ---------- FastAPI App ----------

app = FastAPI(title="Huwei Landmarks LINE BOT")


def _get_parser() -> WebhookParser:
    """Lazy-build parser；延後讀環境變數方便測試覆寫。"""
    return WebhookParser(_require_env("LINE_CHANNEL_SECRET"))


def _get_messaging_config() -> Configuration:
    return Configuration(access_token=_require_env("LINE_CHANNEL_ACCESS_TOKEN"))


def _extract_signature(headers) -> str:
    """LINE header 是 `X-Line-Signature`，但 HTTP header 大小寫不敏感。

    Starlette 的 Headers 介面本身已 case-insensitive，這裡再做一次
    fallback，以防中間經過 reverse proxy 把 header 名稱改成全小寫。
    """
    return (
        headers.get("x-line-signature")
        or headers.get("X-Line-Signature")
        or ""
    )


@app.get("/")
async def root() -> dict:
    return {"service": "huwei-landmarks-line-bot", "status": "ok"}


@app.get("/healthz")
async def healthz() -> PlainTextResponse:
    return PlainTextResponse("ok")


@app.post("/webhook")
async def webhook(request: Request) -> dict:
    """LINE Platform 的 webhook 進入點。"""
    signature = _extract_signature(request.headers)
    body_bytes = await request.body()
    body_text = body_bytes.decode("utf-8")

    parser = _get_parser()
    try:
        events = parser.parse(body_text, signature)
    except InvalidSignatureError:
        logger.warning("Invalid signature on /webhook; rejecting request")
        raise HTTPException(status_code=400, detail="Invalid signature")

    config = _get_messaging_config()
    with ApiClient(config) as api_client:
        messaging_api = MessagingApi(api_client)
        blob_api = MessagingApiBlob(api_client)

        for event in events:
            try:
                _handle_event(event, messaging_api, blob_api)
            except Exception:  # noqa: BLE001
                logger.exception("Failed to handle event: %r", event)

    return {"status": "ok", "events": len(events)}


# ---------- Event routing ----------

def _handle_event(
    event,
    messaging_api: MessagingApi,
    blob_api: MessagingApiBlob,
) -> None:
    """Dispatch single webhook event."""
    if not isinstance(event, MessageEvent):
        logger.debug("Ignoring non-message event: %s", type(event).__name__)
        return

    message = event.message
    reply_token = event.reply_token

    if isinstance(message, ImageMessageContent):
        _handle_image_event(message.id, reply_token, blob_api, messaging_api)
        return

    # 非圖片訊息 — 禮貌回覆一句，讓使用者知道怎麼用
    logger.info("Received unsupported message type: %s", type(message).__name__)
    _reply_text(messaging_api, reply_token, UNSUPPORTED_MESSAGE)


def _handle_image_event(
    message_id: str,
    reply_token: str,
    blob_api: MessagingApiBlob,
    messaging_api: MessagingApi,
) -> None:
    image_bytes = _download_image(blob_api, message_id)
    reply_text = line_bot.handle_image_message(image_bytes)
    _reply_text(messaging_api, reply_token, reply_text)


def _download_image(blob_api: MessagingApiBlob, message_id: str) -> bytes:
    """透過 LINE SDK 下載 image message 內容。

    SDK 回傳 bytearray / bytes，這裡統一成 bytes 方便下游使用。
    """
    content = blob_api.get_message_content(message_id=message_id)
    if isinstance(content, (bytes, bytearray)):
        return bytes(content)
    # SDK 不同版本可能回傳 file-like；做個保底
    read = getattr(content, "read", None)
    if callable(read):
        return read()
    raise TypeError(f"Unexpected content type from LINE blob API: {type(content)!r}")


def _reply_text(messaging_api: MessagingApi, reply_token: Optional[str], text: str) -> None:
    if not reply_token:
        return
    messaging_api.reply_message(
        ReplyMessageRequest(
            reply_token=reply_token,
            messages=[TextMessage(text=text)],
        )
    )


if __name__ == "__main__":  # pragma: no cover
    import uvicorn

    uvicorn.run(
        "apps.huwei_landmarks.server:app",
        host=os.environ.get("HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", "8000")),
        reload=bool(os.environ.get("RELOAD")),
    )

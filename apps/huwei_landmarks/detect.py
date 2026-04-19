"""CLI 入口 — 虎尾地標辨識

從原本的 detect.py 搬過來。核心辨識邏輯改走 RAGPipeline，
HackMD 批次 / 檔案 / URL 這些 I/O 部分原樣保留。

使用方式：
    python -m apps.huwei_landmarks.detect photo.jpg
    python -m apps.huwei_landmarks.detect photo1.jpg photo2.jpg
    python -m apps.huwei_landmarks.detect images/
    python -m apps.huwei_landmarks.detect https://hackmd.io/_uploads/xxx.png
    python -m apps.huwei_landmarks.detect --hackmd https://hackmd.io/@user/note

環境變數（.env）：
    GOOGLE_API_KEY=你的 Gemini 金鑰
    HACKMD_TOKEN=你的 HackMD API Token（選填）
"""

import argparse
import json
import os
import re
import sys

import requests
from dotenv import load_dotenv

from .config import build_pipeline

load_dotenv()


# === HackMD ===

def load_images_from_hackmd(hackmd_url: str) -> list[str]:
    """從 HackMD 頁面抓取所有圖片 URL"""
    match = re.search(r"hackmd\.io/(?:@[^/]+/)?([a-zA-Z0-9_-]+)", hackmd_url)
    if not match:
        print(f"無法解析 HackMD URL：{hackmd_url}")
        return []

    note_id = match.group(1)
    hackmd_token = os.getenv("HACKMD_TOKEN")

    if hackmd_token:
        resp = requests.get(
            f"https://api.hackmd.io/v1/notes/{note_id}",
            headers={"Authorization": f"Bearer {hackmd_token}"},
        )
        if resp.status_code == 200:
            content = resp.json().get("content", "")
        else:
            print(f"  HackMD API 失敗（{resp.status_code}），改用公開下載")
            resp = requests.get(f"https://hackmd.io/{note_id}/download")
            content = resp.text
    else:
        resp = requests.get(f"https://hackmd.io/{note_id}/download")
        content = resp.text

    urls = re.findall(
        r"https://hackmd\.io/_uploads/[a-zA-Z0-9_-]+\.(?:png|jpg|jpeg)",
        content,
    )

    seen: set[str] = set()
    unique: list[str] = []
    for url in urls:
        if url not in seen:
            seen.add(url)
            unique.append(url)
    return unique


# === 圖片載入 ===

def load_image_from_file(path: str) -> bytes:
    with open(path, "rb") as f:
        return f.read()


def load_image_from_url(url: str) -> bytes:
    resp = requests.get(url)
    resp.raise_for_status()
    return resp.content


# === Main ===

def main():
    parser = argparse.ArgumentParser(description="虎尾地標辨識 (RAG Kit)")
    parser.add_argument("images", nargs="*", help="圖片檔案、資料夾或 URL")
    parser.add_argument("--hackmd", help="從 HackMD 頁面批次載入圖片")
    parser.add_argument("--key", default=os.getenv("GOOGLE_API_KEY"), help="Gemini API Key")
    parser.add_argument("--csv", help="改用本地 CSV 作為 DataSource（預設用 Google Sheet）")
    args = parser.parse_args()

    if not args.key:
        print("錯誤：請在 .env 設定 GOOGLE_API_KEY，或用 --key 指定")
        sys.exit(1)

    if not args.images and not args.hackmd:
        print("錯誤：請提供圖片或 --hackmd URL")
        parser.print_help()
        sys.exit(1)

    print("建立 RAG pipeline...")
    pipeline = build_pipeline(api_key=args.key, csv_path=args.csv)
    print(f"載入 {len(pipeline.retriever.retrieve(None))} 個地點\n")

    # 收集圖片 tasks
    tasks: list[tuple[str, str]] = []

    if args.hackmd:
        print(f"從 HackMD 載入圖片：{args.hackmd}")
        urls = load_images_from_hackmd(args.hackmd)
        print(f"找到 {len(urls)} 張圖片\n")
        for url in urls:
            tasks.append(("url", url))

    for path in args.images:
        if path.startswith("http://") or path.startswith("https://"):
            tasks.append(("url", path))
        elif os.path.isdir(path):
            for f in sorted(os.listdir(path)):
                if f.lower().endswith((".jpg", ".jpeg", ".png")):
                    tasks.append(("file", os.path.join(path, f)))
        elif os.path.isfile(path):
            tasks.append(("file", path))
        else:
            print(f"找不到：{path}")

    if not tasks:
        print("沒有找到任何圖片")
        sys.exit(1)

    # 逐張辨識
    results: list[dict] = []
    for i, (source_type, source) in enumerate(tasks, 1):
        label = os.path.basename(source) if source_type == "file" else source.split("/")[-1]
        print(f"[{i}/{len(tasks)}] {label}")

        try:
            if source_type == "file":
                image_bytes = load_image_from_file(source)
            else:
                image_bytes = load_image_from_url(source)

            raw = pipeline.run({"image_bytes": image_bytes, "mime_type": "image/png"})
            result = json.loads(raw)

            if "error" in result:
                print(f"  錯誤：{result['error']}")
            else:
                print(f"  地點：{result['name']}")
                print(f"  依據：{result['reason']}")
                print(f"  信心：{result.get('confidence', 'N/A')}")
                results.append(result)
        except Exception as e:
            print(f"  錯誤：{e}")

        print()

    if results:
        print("=" * 50)
        print(f"  辨識完成：{len(results)}/{len(tasks)} 張")
        print("=" * 50)
        for i, r in enumerate(results, 1):
            print(f"  {i}. {r['name']} ({r.get('confidence', '?')})")


if __name__ == "__main__":
    main()

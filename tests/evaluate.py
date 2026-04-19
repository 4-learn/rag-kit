"""Golden 評估腳本

用一組 golden image → 預期地點 的資料集跑 pipeline，計算準確率。

執行方式：
    python tests/evaluate.py
    python tests/evaluate.py --golden data/golden/landmarks.jsonl

Golden 檔格式 (JSONL)：
    {"image": "path/to/image.jpg", "expected": "雲林布袋戲館"}
    {"image": "https://...", "expected": "虎尾糖廠"}

若 golden 檔不存在或是空，腳本會 exit 0 並提示（不會當 fail）。
"""

import argparse
import json
import os
import sys
from pathlib import Path

import requests

# 讓 tests/ 能 import 到 src/ 與 apps/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from apps.huwei_landmarks.config import build_pipeline  # noqa: E402


def load_image(path_or_url: str) -> bytes:
    if path_or_url.startswith(("http://", "https://")):
        resp = requests.get(path_or_url)
        resp.raise_for_status()
        return resp.content
    with open(path_or_url, "rb") as f:
        return f.read()


def run_evaluation(golden_path: Path, api_key: str | None = None) -> dict:
    if not golden_path.exists():
        print(f"Golden 檔不存在：{golden_path}")
        print("（跳過評估——這是 ok 的，等資料補上再跑）")
        return {"total": 0, "correct": 0, "score": 0.0, "skipped": True}

    lines = [ln for ln in golden_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    if not lines:
        print(f"Golden 檔是空的：{golden_path}（跳過）")
        return {"total": 0, "correct": 0, "score": 0.0, "skipped": True}

    pipeline = build_pipeline(api_key=api_key)
    total = 0
    correct = 0

    for line in lines:
        case = json.loads(line)
        image = case["image"]
        expected = case["expected"]

        try:
            image_bytes = load_image(image)
            raw = pipeline.run({"image_bytes": image_bytes, "mime_type": "image/png"})
            result = json.loads(raw)
            got = result.get("name", "")
        except Exception as e:
            print(f"  [ERROR] {image}: {e}")
            total += 1
            continue

        total += 1
        ok = got == expected
        if ok:
            correct += 1
        print(f"  [{'OK' if ok else 'XX'}] {image} → 預期={expected} 實際={got}")

    score = correct / total if total else 0.0
    return {"total": total, "correct": correct, "score": score, "skipped": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--golden",
        default="data/golden/landmarks.jsonl",
        help="Golden 資料集路徑 (JSONL)",
    )
    parser.add_argument("--key", default=os.getenv("GOOGLE_API_KEY"))
    args = parser.parse_args()

    result = run_evaluation(Path(args.golden), api_key=args.key)
    if result["skipped"]:
        print("評估略過。")
        return 0

    print()
    print("=" * 50)
    print(f"  評估結果：{result['correct']}/{result['total']} = {result['score']:.2%}")
    print("=" * 50)
    return 0


if __name__ == "__main__":
    sys.exit(main())

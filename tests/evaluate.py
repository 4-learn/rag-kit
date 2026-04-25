"""Golden 評估腳本（PR-time 自動評分用）

用 `data/golden/` 底下的照片跑 pipeline，計算辨識準確率。

檔名 pattern：`{地標名}-{編號}-{來源}.{ext}`，例：
    虎尾驛-1-wiki.jpg            → expected = 虎尾驛
    雲林布袋戲館-2-commons.jpg   → expected = 雲林布袋戲館

執行方式：
    python tests/evaluate.py                       # 預設 markdown 給人看
    python tests/evaluate.py --output=json         # 給 CI 解析
    python tests/evaluate.py --limit 3             # 只跑 3 張（debug）

為了避免燒爆 free tier 配額（20 RPD），預設只挑 5 張代表照片。
若要全跑，指定 `--limit 0`（請斟酌）。
"""

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

# 讓 tests/ 能 import 到 src/ 與 apps/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from apps.huwei_landmarks.config import build_pipeline  # noqa: E402

GOLDEN_DIR = Path(__file__).resolve().parent.parent / "data" / "golden"
IMAGE_EXTS = {".jpg", ".jpeg", ".png"}

# 預設挑這幾個地標當代表（free-tier safe）；
# 合同廳舍 是台南照片，不在挑選名單內（避免 informational noise）。
PREFERRED_LANDMARKS = [
    "虎尾驛",
    "虎尾糖廠",
    "虎尾鐵橋",
    "雲林布袋戲館",
    "雲林故事館",
]

EXPECTED_RE = re.compile(r"^(.+?)-\d")


def expected_from_filename(name: str) -> str | None:
    """從 `虎尾驛-1-wiki.jpg` 取出 `虎尾驛`。"""
    stem = Path(name).stem
    m = EXPECTED_RE.match(stem)
    return m.group(1) if m else None


def list_golden_photos(golden_dir: Path) -> list[Path]:
    if not golden_dir.exists():
        return []
    return sorted(
        p
        for p in golden_dir.iterdir()
        if p.is_file() and p.suffix.lower() in IMAGE_EXTS
    )


def select_photos(photos: list[Path], limit: int) -> list[Path]:
    """挑出最多 `limit` 張代表照片。

    優先從 PREFERRED_LANDMARKS 各挑 1 張（按字母序的第一個檔），
    名單湊不滿時，再從剩下的照片補（但跳過 `合同廳舍`）。
    limit=0 表示「全跑」。
    """
    if limit <= 0:
        return photos

    by_landmark: dict[str, list[Path]] = {}
    for p in photos:
        expected = expected_from_filename(p.name)
        if not expected:
            continue
        by_landmark.setdefault(expected, []).append(p)

    selected: list[Path] = []
    used: set[Path] = set()

    for landmark in PREFERRED_LANDMARKS:
        candidates = by_landmark.get(landmark, [])
        if candidates:
            chosen = candidates[0]
            selected.append(chosen)
            used.add(chosen)
        if len(selected) >= limit:
            return selected[:limit]

    # 補滿（跳過 合同廳舍 — 台南照片）
    for p in photos:
        if p in used:
            continue
        if expected_from_filename(p.name) == "合同廳舍":
            continue
        selected.append(p)
        if len(selected) >= limit:
            break

    return selected[:limit]


def mime_type_for(path: Path) -> str:
    ext = path.suffix.lower()
    if ext == ".png":
        return "image/png"
    return "image/jpeg"


def run_one(pipeline, photo: Path) -> dict:
    expected = expected_from_filename(photo.name) or ""
    mime = mime_type_for(photo)
    started = time.monotonic()
    got = ""
    error: str | None = None
    try:
        image_bytes = photo.read_bytes()
        raw = pipeline.run({"image_bytes": image_bytes, "mime_type": mime})
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict) and parsed.get("error"):
                # Pipeline 把上游錯誤包成 {"error": "..."}（例：quota exceeded）
                msg = str(parsed["error"])
                # 砍長訊息，留可辨識前綴
                error = msg.split("\n", 1)[0][:80]
            else:
                got = str(parsed.get("name", "")).strip() if isinstance(parsed, dict) else ""
                if not got and not error:
                    error = "no-name-field"
        except (json.JSONDecodeError, AttributeError):
            # Generator 偶爾包 markdown — 算 parse 失敗
            error = "json-parse-failed"
            got = raw[:60] if isinstance(raw, str) else ""
    except Exception as e:  # noqa: BLE001
        error = f"{type(e).__name__}: {e}"
    latency = time.monotonic() - started
    ok = bool(got) and got == expected
    return {
        "photo": photo.name,
        "expected": expected,
        "got": got,
        "ok": ok,
        "latency_seconds": round(latency, 2),
        "error": error,
    }


def render_json(summary: dict) -> str:
    return json.dumps(summary, ensure_ascii=False, indent=2)


def render_markdown(summary: dict) -> str:
    total = summary["total"]
    correct = summary["correct"]
    pct = (correct / total * 100) if total else 0.0
    avg = summary["avg_latency_seconds"]

    lines = []
    lines.append("## 🤖 Golden Evaluation")
    lines.append("")
    if total == 0:
        lines.append("_找不到 `data/golden/` 底下的照片，跳過評估。_")
        return "\n".join(lines)
    lines.append(f"**Score**: {correct}/{total} ({pct:.0f}%)")
    lines.append(f"**Avg latency**: {avg:.1f}s")
    lines.append("")
    lines.append("| Photo | Expected | Got | Time |")
    lines.append("|-------|----------|-----|------|")
    for r in summary["results"]:
        if r["error"] and not r["got"]:
            got_cell = f"⚠ {r['error']}"
        else:
            mark = "✅" if r["ok"] else "❌"
            got_cell = f"{mark} {r['got']}" if r["got"] else f"{mark} (空)"
        lines.append(
            f"| {r['photo']} | {r['expected']} | {got_cell} | {r['latency_seconds']:.0f}s |"
        )
    lines.append("")
    lines.append(
        f"_跑了 {total} 張代表照片（free-tier safe）；完整 21 張請手動跑 "
        "`python tests/evaluate.py --limit 0`。_"
    )
    return "\n".join(lines)


def evaluate(limit: int, api_key: str | None) -> dict:
    photos = list_golden_photos(GOLDEN_DIR)
    selected = select_photos(photos, limit)

    if not selected:
        return {
            "total": 0,
            "correct": 0,
            "score": 0.0,
            "avg_latency_seconds": 0.0,
            "results": [],
            "skipped": True,
            "reason": "no-photos",
        }

    pipeline = build_pipeline(api_key=api_key)
    results = [run_one(pipeline, p) for p in selected]

    total = len(results)
    correct = sum(1 for r in results if r["ok"])
    avg_latency = sum(r["latency_seconds"] for r in results) / total if total else 0.0

    return {
        "total": total,
        "correct": correct,
        "score": (correct / total) if total else 0.0,
        "avg_latency_seconds": round(avg_latency, 2),
        "results": results,
        "skipped": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        choices=("markdown", "json"),
        default="markdown",
        help="輸出格式（預設 markdown）",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=5,
        help="最多跑幾張（free-tier safe 預設 5；0=全跑）",
    )
    parser.add_argument(
        "--api-key",
        default=os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"),
        help="Gemini API key（預設讀 GEMINI_API_KEY / GOOGLE_API_KEY env）",
    )
    args = parser.parse_args()

    if not args.api_key:
        # markdown 模式仍輸出可讀訊息，但 exit 1 以利 CI 偵測
        print("## 🤖 Golden Evaluation\n\n_缺少 `GEMINI_API_KEY`，跳過評估。_")
        return 1

    summary = evaluate(args.limit, args.api_key)

    if args.output == "json":
        print(render_json(summary))
    else:
        print(render_markdown(summary))

    return 0


if __name__ == "__main__":
    sys.exit(main())

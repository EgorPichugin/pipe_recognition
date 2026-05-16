#!/usr/bin/env python3
"""Local OCR runner: extract visible text from photos with EasyOCR.

Writes one JSON file per image into ``out/ocr/``. The JSON preserves the
on-photo line order, grouped into visual blocks by their position on the
image (top/middle/bottom × left/center/right).

No external APIs. First run downloads EasyOCR model weights (~100MB per
language) into ``~/.EasyOCR/`` — after that everything is offline.

Usage:
    python scripts/ocr_images.py                       # 5 images, langs=de,en
    python scripts/ocr_images.py --limit 10
    python scripts/ocr_images.py --langs de,en,ru
    python scripts/ocr_images.py --source path/to/one.jpg --limit 0
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = Path("/Users/olegkulikov/Desktop/hackathon Vienna/Beispiele")
DEFAULT_OUT = REPO_ROOT / "out" / "ocr"
DEFAULT_LIMIT = 5
DEFAULT_LANGS = "de,en"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def iter_image_files(source: Path) -> list[Path]:
    if source.is_file():
        return [source]
    if not source.is_dir():
        return []
    return sorted(
        p for p in source.rglob("*")
        if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS
    )


def output_stem_for(image_path: Path, source_root: Path) -> str:
    try:
        relative = image_path.relative_to(source_root)
    except ValueError:
        relative = Path(image_path.name)
    return "__".join(relative.with_suffix("").parts)


def bbox_metrics(bbox: list[list[float]]) -> dict[str, float]:
    xs = [float(p[0]) for p in bbox]
    ys = [float(p[1]) for p in bbox]
    return {
        "x_left": min(xs),
        "x_right": max(xs),
        "y_top": min(ys),
        "y_bottom": max(ys),
        "y_center": sum(ys) / len(ys),
        "height": max(ys) - min(ys),
    }


def group_into_lines(detections: list[tuple]) -> list[list[tuple]]:
    """Cluster detections into lines by Y, sort within line by X."""
    if not detections:
        return []
    enriched = [(d, bbox_metrics(d[0])) for d in detections]
    enriched.sort(key=lambda e: e[1]["y_center"])
    median_h = statistics.median(e[1]["height"] for e in enriched) or 1.0
    threshold = median_h * 0.6

    lines: list[list[tuple]] = []
    current: list[tuple] = []
    running_y = None
    for det_metrics in enriched:
        m = det_metrics[1]
        if running_y is None or abs(m["y_center"] - running_y) <= threshold:
            current.append(det_metrics)
        else:
            current.sort(key=lambda e: e[1]["x_left"])
            lines.append(current)
            current = [det_metrics]
        running_y = sum(e[1]["y_center"] for e in current) / len(current)
    if current:
        current.sort(key=lambda e: e[1]["x_left"])
        lines.append(current)
    return lines


def group_lines_into_blocks(lines: list[list[tuple]]) -> list[list[dict]]:
    """Split lines into blocks at vertical gaps larger than 2x median line height."""
    if not lines:
        return []
    line_metrics: list[dict] = []
    for line in lines:
        line_metrics.append({
            "y_top": min(m["y_top"] for _, m in line),
            "y_bottom": max(m["y_bottom"] for _, m in line),
            "x_left": min(m["x_left"] for _, m in line),
            "x_right": max(m["x_right"] for _, m in line),
            "line": line,
        })
    median_h = statistics.median(lm["y_bottom"] - lm["y_top"] for lm in line_metrics) or 1.0
    gap_threshold = median_h * 2.0

    blocks: list[list[dict]] = [[line_metrics[0]]]
    for prev, curr in zip(line_metrics, line_metrics[1:]):
        if curr["y_top"] - prev["y_bottom"] > gap_threshold:
            blocks.append([curr])
        else:
            blocks[-1].append(curr)
    return blocks


def position_label(block: list[dict], image_w: int, image_h: int) -> str:
    cy = (min(lm["y_top"] for lm in block) + max(lm["y_bottom"] for lm in block)) / 2 / image_h
    cx = (min(lm["x_left"] for lm in block) + max(lm["x_right"] for lm in block)) / 2 / image_w
    v = "top" if cy < 0.33 else ("middle" if cy < 0.66 else "bottom")
    h = "left" if cx < 0.33 else ("center" if cx < 0.66 else "right")
    return f"{v}_{h}"


def build_blocks(detections: list[tuple], image_w: int, image_h: int) -> list[dict]:
    lines = group_into_lines(detections)
    block_groups = group_lines_into_blocks(lines)
    out_blocks: list[dict] = []
    for block in block_groups:
        block_lines: list[str] = []
        confs: list[float] = []
        for lm in block:
            texts = [det[1] for det, _ in lm["line"]]
            line_confs = [float(det[2]) for det, _ in lm["line"]]
            block_lines.append(" ".join(t.strip() for t in texts if t.strip()))
            confs.extend(line_confs)
        out_blocks.append({
            "region": position_label(block, image_w, image_h),
            "lines": [ln for ln in block_lines if ln],
            "avg_confidence": round(sum(confs) / len(confs), 3) if confs else 0.0,
        })
    return out_blocks


def run_ocr(reader, image_path: Path) -> tuple[list[tuple], int, int]:
    with Image.open(image_path) as img:
        img = img.convert("RGB")
        w, h = img.size
        arr = np.array(img)
    detections = reader.readtext(arr)
    return detections, w, h


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE, help="Folder (scanned recursively) or single image.")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="Output folder for per-image JSON files.")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT, help="Process at most this many images. 0 = no limit.")
    parser.add_argument("--langs", default=DEFAULT_LANGS, help="Comma-separated EasyOCR language codes (e.g. 'de,en' or 'de,en,ru').")
    parser.add_argument("--gpu", action="store_true", help="Try to use GPU (default: CPU).")
    args = parser.parse_args()

    try:
        import easyocr
    except ImportError:
        print("ERROR: easyocr is not installed. Run: pip install easyocr", file=sys.stderr)
        return 1

    images = iter_image_files(args.source)
    if not images:
        print(f"No images found in {args.source}", file=sys.stderr)
        return 1
    if args.limit and args.limit > 0:
        images = images[: args.limit]

    args.out.mkdir(parents=True, exist_ok=True)
    source_root = args.source if args.source.is_dir() else args.source.parent
    languages = [lang.strip() for lang in args.langs.split(",") if lang.strip()]

    print(f"Engine: EasyOCR  langs={languages}  gpu={args.gpu}")
    print(f"Source: {args.source}")
    print(f"Out:    {args.out}")
    print(f"Images: {len(images)}")
    print("Loading EasyOCR reader (first run downloads model weights)...")
    reader = easyocr.Reader(languages, gpu=args.gpu)
    print("Reader ready.\n")

    failures = 0
    for idx, image_path in enumerate(images, 1):
        stem = output_stem_for(image_path, source_root)
        print(f"[{idx}/{len(images)}] {stem} ... ", end="", flush=True)
        try:
            detections, w, h = run_ocr(reader, image_path)
            blocks = build_blocks(detections, w, h)
        except Exception as exc:  # noqa: BLE001
            failures += 1
            print(f"FAILED: {exc}")
            continue

        result = {
            "image": image_path.name,
            "source_path": str(image_path),
            "image_size": {"width": w, "height": h},
            "engine": "easyocr",
            "languages": languages,
            "processed_at": datetime.now(timezone.utc).isoformat(),
            "blocks": blocks,
        }
        out_path = args.out / f"{stem}.json"
        out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        line_count = sum(len(b["lines"]) for b in blocks)
        print(f"OK ({len(blocks)} blocks, {line_count} lines) -> {out_path.name}")

    print(f"\nDone. Success: {len(images) - failures}, Failed: {failures}")
    return 0 if failures == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())

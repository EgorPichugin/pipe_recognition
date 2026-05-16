#!/usr/bin/env python3
"""Extract GPS coordinates using PaddleOCR.

PaddleOCR's Latin/German model recognises ``°`` and ``'`` properly, unlike
EasyOCR's en/de models. Strategy:
1. Crop top and bottom bands (full width, 40% height each).
2. Upscale 2x for crisper glyphs.
3. Run PaddleOCR — no character allowlist needed; let the model decide.
4. Regex-parse for DMS or decimal coordinate patterns.
5. Validate against Austria coordinate range.

Writes one JSON per image to ``out/gps_paddle/<stem>.json``.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = Path("/Users/olegkulikov/Desktop/hackathon Vienna/Beispiele")
DEFAULT_OUT = REPO_ROOT / "out" / "gps_paddle"
DEFAULT_LIMIT = 5

BAND_HEIGHT_FRAC = 0.40
UPSCALE = 2.0

AUSTRIA_LAT = (46.0, 49.5)
AUSTRIA_LON = (9.0, 17.5)

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}

# DMS: e.g. "46°33'56.238\"N" — also tolerate ``*`` or ``o`` for ``°`` and
# space/apostrophe for minute marker.
DMS_RE = re.compile(
    r"(\d{1,3})\s*[°*o]\s*(\d{1,2})\s*['′\s]\s*(\d{1,2})\s*[.,]\s*(\d+)\s*[\"″]?\s*([NSEW])",
    re.IGNORECASE,
)
DECIMAL_RE = re.compile(
    r"(\d{1,3})\s*[.,]\s*(\d{4,})\s*([NSEW])",
    re.IGNORECASE,
)


def dms_to_decimal(deg: str, minutes: str, sec_int: str, sec_frac: str, hemi: str) -> float:
    seconds = float(f"{sec_int}.{sec_frac}")
    val = int(deg) + int(minutes) / 60 + seconds / 3600
    if hemi.upper() in ("S", "W"):
        val = -val
    return round(val, 7)


def parse_coordinates(text: str) -> dict:
    found: dict[str, dict] = {}
    for m in DMS_RE.finditer(text):
        deg, minutes, sec_int, sec_frac, hemi = m.groups()
        try:
            val = dms_to_decimal(deg, minutes, sec_int, sec_frac, hemi)
        except (ValueError, ZeroDivisionError):
            continue
        key = "lat" if hemi.upper() in ("N", "S") else "lon"
        if key not in found:
            found[key] = {"value": val, "raw": m.group(0).strip(), "format": "dms"}

    for m in DECIMAL_RE.finditer(text):
        deg, frac, hemi = m.groups()
        try:
            val = float(f"{deg}.{frac}")
        except ValueError:
            continue
        if hemi.upper() in ("S", "W"):
            val = -val
        val = round(val, 7)
        key = "lat" if hemi.upper() in ("N", "S") else "lon"
        if key not in found:
            found[key] = {"value": val, "raw": m.group(0).strip(), "format": "decimal"}
    return found


def validate_austria(coords: dict) -> dict:
    valid: dict[str, dict] = {}
    if "lat" in coords:
        v = coords["lat"]["value"]
        if AUSTRIA_LAT[0] <= v <= AUSTRIA_LAT[1]:
            valid["lat"] = coords["lat"]
    if "lon" in coords:
        v = coords["lon"]["value"]
        if AUSTRIA_LON[0] <= v <= AUSTRIA_LON[1]:
            valid["lon"] = coords["lon"]
    return valid


def crop_bands(img: Image.Image) -> dict[str, Image.Image]:
    w, h = img.size
    bh = int(h * BAND_HEIGHT_FRAC)
    return {
        "top_band": img.crop((0, 0, w, bh)),
        "bottom_band": img.crop((0, h - bh, w, h)),
    }


def upscale(img: Image.Image, factor: float = UPSCALE) -> Image.Image:
    w, h = img.size
    return img.resize((int(w * factor), int(h * factor)), Image.LANCZOS)


def run_paddle(ocr, band: Image.Image) -> list[tuple]:
    """Run PaddleOCR on a band image. Returns list of (text, confidence).

    Handles both legacy (``ocr.ocr``) and newer (``ocr.predict``) APIs.
    """
    arr = np.array(band.convert("RGB"))
    results: list[tuple] = []
    if hasattr(ocr, "predict"):
        # PaddleOCR 3.x
        preds = ocr.predict(arr)
        for pred in preds:
            if isinstance(pred, dict):
                texts = pred.get("rec_texts", []) or pred.get("rec_text", [])
                scores = pred.get("rec_scores", []) or pred.get("rec_score", [])
                for t, s in zip(texts, scores):
                    results.append((t, float(s)))
            else:
                for line in pred:
                    if not line:
                        continue
                    _, (text, conf) = line[0], line[1]
                    results.append((text, float(conf)))
    else:
        # PaddleOCR <= 2.x
        preds = ocr.ocr(arr)
        if preds and preds[0]:
            for line in preds[0]:
                if not line:
                    continue
                _bbox, (text, conf) = line
                results.append((text, float(conf)))
    return results


def iter_images(source: Path) -> list[Path]:
    if source.is_file():
        return [source]
    if not source.is_dir():
        return []
    return sorted(p for p in source.rglob("*") if p.is_file() and p.suffix.lower() in IMAGE_EXTS)


def output_stem_for(image_path: Path, source_root: Path) -> str:
    try:
        relative = image_path.relative_to(source_root)
    except ValueError:
        relative = Path(image_path.name)
    return "__".join(relative.with_suffix("").parts)


def build_paddle_ocr(lang: str):
    from paddleocr import PaddleOCR

    # Force PP-OCRv5 mobile detection model — much lighter than the server variant
    # and CPU-friendly. Server model OOMs on a MacBook Air with our band sizes.
    mobile_models = {
        "text_detection_model_name": "PP-OCRv5_mobile_det",
        "text_recognition_model_name": "latin_PP-OCRv5_mobile_rec",
    }
    common = {"lang": lang}
    for kwargs in (
        {**mobile_models, "use_textline_orientation": True},
        {**mobile_models, "use_angle_cls": True},
        mobile_models,
        # Fallback: let Paddle pick models if name-based init fails on this version.
        {"use_textline_orientation": True},
        {"use_angle_cls": True},
        {},
    ):
        try:
            return PaddleOCR(**common, **kwargs)
        except (TypeError, ValueError):
            continue
    return PaddleOCR(**common)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    parser.add_argument("--lang", default="german", help="PaddleOCR language (e.g. german, en, latin).")
    args = parser.parse_args()

    try:
        import paddleocr  # noqa: F401
    except ImportError:
        print("ERROR: paddleocr not installed. pip install paddlepaddle paddleocr", file=sys.stderr)
        return 1

    images = iter_images(args.source)
    if not images:
        print(f"No images in {args.source}", file=sys.stderr)
        return 1
    if args.limit and args.limit > 0:
        images = images[: args.limit]

    args.out.mkdir(parents=True, exist_ok=True)
    source_root = args.source if args.source.is_dir() else args.source.parent

    print(f"Loading PaddleOCR (lang={args.lang})... first run downloads models")
    ocr = build_paddle_ocr(args.lang)
    print(f"Processing {len(images)} images.\n")

    failures = 0
    for idx, image_path in enumerate(images, 1):
        stem = output_stem_for(image_path, source_root)
        print(f"[{idx}/{len(images)}] {stem} ... ", end="", flush=True)
        try:
            with Image.open(image_path) as img:
                img = img.convert("RGB")
                bands = crop_bands(img)

            band_results: dict[str, dict] = {}
            for band_name, band_img in bands.items():
                # No upscale: Paddle handles native resolution well; upscaling triggers OOM.
                detections = run_paddle(ocr, band_img)
                texts = [d[0] for d in detections]
                joined = " ".join(texts)
                parsed = parse_coordinates(joined)
                validated = validate_austria(parsed)
                band_results[band_name] = {
                    "raw_lines": texts,
                    "joined": joined,
                    "parsed": parsed,
                    "validated_austria": validated,
                }

            best_band = None
            for name, br in band_results.items():
                if "lat" in br["validated_austria"] and "lon" in br["validated_austria"]:
                    best_band = name
                    break
            if not best_band:
                for name, br in band_results.items():
                    if br["validated_austria"]:
                        best_band = name
                        break

            final = band_results[best_band]["validated_austria"] if best_band else {}
            result = {
                "image": image_path.name,
                "source_path": str(image_path),
                "engine": "paddleocr",
                "lang": args.lang,
                "best_band": best_band,
                "gps": final,
                "bands": band_results,
                "processed_at": datetime.now(timezone.utc).isoformat(),
            }
            out_path = args.out / f"{stem}.json"
            out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

            lat = final.get("lat", {}).get("value")
            lon = final.get("lon", {}).get("value")
            if lat is not None and lon is not None:
                print(f"OK band={best_band} lat={lat} lon={lon}")
            elif lat is not None or lon is not None:
                print(f"PARTIAL band={best_band} lat={lat} lon={lon}")
            else:
                print("NO GPS")
        except Exception as exc:  # noqa: BLE001
            failures += 1
            print(f"FAILED: {exc}")

    print(f"\nDone. Processed: {len(images) - failures}, Failed: {failures}")
    return 0 if failures == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())

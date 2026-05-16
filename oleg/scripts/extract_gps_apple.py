#!/usr/bin/env python3
"""Extract GPS coordinates from photo watermarks using Apple Vision OCR.

Apple Vision (the OCR engine behind macOS Preview, Photos, and Live Text) is
trained on real-world imagery and handles construction-site overlay text much
better than EasyOCR. It recognises ``°``, ``'``, ``"`` and German diacritics
out of the box, eliminating the ``°→*``, ``°→9``, and ``5→6`` misreads we had
to work around with EasyOCR.

Strategy: feed the full image to Vision (it's fast — Neural Engine on Apple
Silicon), parse every detected line with the existing regex set from
``extract_gps.py``, then validate against Austria's bounding box.

Output is the same normalised JSON: per coordinate, both decimal degrees and
DMS string, plus the raw OCR text and detected format.

macOS-only — relies on Apple's Vision.framework via the ``ocrmac`` wrapper.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from ocrmac import ocrmac

# Reuse the parser/validator we already wrote for the EasyOCR script.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from extract_gps import (  # noqa: E402
    AUSTRIA_LAT,
    AUSTRIA_LON,
    parse_coordinates,
    validate_austria,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = Path("/Users/olegkulikov/Desktop/hackathon Vienna/Beispiele/geo")
DEFAULT_OUT = REPO_ROOT / "out" / "gps_apple"
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}


def iter_images(source: Path) -> list[Path]:
    if source.is_file():
        return [source]
    if not source.is_dir():
        return []
    return sorted(p for p in source.rglob("*") if p.is_file() and p.suffix.lower() in IMAGE_EXTS)


def output_stem(image_path: Path, source_root: Path) -> str:
    try:
        rel = image_path.relative_to(source_root)
    except ValueError:
        rel = Path(image_path.name)
    return "__".join(rel.with_suffix("").parts)


def decimal_to_dms(value: float, hemi_axis: str) -> str:
    """Convert decimal degrees to a DMS string like '46°33'56.238\"N'.

    hemi_axis is 'lat' or 'lon' — used only to pick N/S vs E/W from the sign.
    """
    if hemi_axis == "lat":
        hemi = "N" if value >= 0 else "S"
    else:
        hemi = "E" if value >= 0 else "W"
    value = abs(value)
    deg = int(value)
    minutes_full = (value - deg) * 60
    minutes = int(minutes_full)
    seconds = round((minutes_full - minutes) * 60, 5)
    return f"{deg}°{minutes}'{seconds}\"{hemi}"


def normalise_coord(parsed: dict, axis: str) -> dict:
    """Take a parsed coord entry (from extract_gps.parse_coordinates) and
    enrich it with both decimal and DMS string representations.
    """
    out = {
        "decimal": parsed["value"],
        "dms": decimal_to_dms(parsed["value"], axis),
        "raw_ocr": parsed["raw"],
        "format_detected": parsed["format"],
    }
    return out


def run_vision(image_path: Path) -> list[tuple[str, float, list]]:
    return ocrmac.OCR(
        str(image_path),
        recognition_level="accurate",
        language_preference=["de-DE", "en-US"],
    ).recognize()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--limit", type=int, default=0, help="Process at most N images. 0 = all.")
    args = parser.parse_args()

    images = iter_images(args.source)
    if not images:
        print(f"No images in {args.source}", file=sys.stderr)
        return 1
    if args.limit and args.limit > 0:
        images = images[: args.limit]

    args.out.mkdir(parents=True, exist_ok=True)
    source_root = args.source if args.source.is_dir() else args.source.parent

    print(f"Engine: Apple Vision (via ocrmac)")
    print(f"Source: {args.source}")
    print(f"Out:    {args.out}")
    print(f"Images: {len(images)}\n")

    failures = 0
    for idx, image_path in enumerate(images, 1):
        stem = output_stem(image_path, source_root)
        print(f"[{idx}/{len(images)}] {stem} ... ", end="", flush=True)
        try:
            detections = run_vision(image_path)
            lines = [t for t, _conf, _bbox in detections]
            joined = " ".join(lines)
            parsed = parse_coordinates(joined)
            validated = validate_austria(parsed)
        except Exception as exc:  # noqa: BLE001
            failures += 1
            print(f"FAILED: {exc}")
            continue

        gps: dict = {}
        if "lat" in validated:
            gps["lat"] = normalise_coord(validated["lat"], "lat")
        if "lon" in validated:
            gps["lon"] = normalise_coord(validated["lon"], "lon")

        result = {
            "image": image_path.name,
            "source_path": str(image_path),
            "engine": "apple_vision",
            "gps": gps,
            "raw_lines": lines,
            "validation_bbox_austria": {
                "lat": list(AUSTRIA_LAT),
                "lon": list(AUSTRIA_LON),
            },
            "processed_at": datetime.now(timezone.utc).isoformat(),
        }
        out_path = args.out / f"{stem}.json"
        out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

        lat = gps.get("lat", {}).get("decimal")
        lon = gps.get("lon", {}).get("decimal")
        if lat is not None and lon is not None:
            print(f"OK lat={lat} lon={lon}")
        elif lat or lon:
            print(f"PARTIAL lat={lat} lon={lon}")
        else:
            print("NO GPS")

    print(f"\nDone. Processed: {len(images) - failures}, Failed: {failures}")
    return 0 if failures == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())

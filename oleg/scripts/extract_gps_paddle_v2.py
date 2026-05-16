#!/usr/bin/env python3
"""Extract GPS from photo watermarks with PaddleOCR mobile + 3-flag confidence.

Outputs an ``overall_flag`` per image:
- ``GPS_HIGH``    — both coordinates parsed, clean format, OCR conf >= threshold,
                    and DMS math is strictly valid (min<60, sec<60). Should be
                    trusted as exactly matching the watermark.
- ``GPS_LOW``     — coordinates parsed but at least one criterion failed
                    (used a fallback regex / no real ``°`` / low OCR conf /
                    only one of lat/lon found). Coordinates exist, but may be
                    off by a few metres to ~hundreds of metres.
- ``NO_GPS``      — nothing parsed at all.

Per-coordinate enrichment:
- ``decimal`` — value in decimal degrees
- ``dms``     — human-readable DMS string built from the decimal value
- ``raw_ocr`` — the exact OCR substring that matched
- ``format``  — which regex pattern matched (strict ``dms`` / ``decimal``
                are clean; the others are rescue patterns)
- ``ocr_confidence`` — Paddle's confidence for the source line
- ``flag``    — HIGH or LOW for this single coord
- ``flag_reason`` — why HIGH or LOW
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

sys.path.insert(0, str(Path(__file__).resolve().parent))
from extract_gps import (  # noqa: E402
    AUSTRIA_LAT,
    AUSTRIA_LON,
    StrictDmsError,
    crop_bands,
    parse_coordinates,
    validate_austria,
)
from gemini_gps_fallback import (  # noqa: E402
    GeminiFallbackError,
    run_gemini_fallback,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = Path("/Users/olegkulikov/Desktop/hackathon Vienna/photo/GeoData")
DEFAULT_OUT = REPO_ROOT / "out" / "gps_paddle_v2"
DEFAULT_OCR_THRESHOLD = 0.90  # provisional — we will calibrate on this run
# Clean formats: unambiguous parse from the OCR string. HIGH-eligible.
# Includes:
#   - dms                                — full strict DMS with ° ' "
#   - decimal                            — decimal-degrees with explicit hemi
#   - dms_min_sec_joined                 — like dms but ' between min/sec missing;
#                                          4 digits after ° split unambiguously
#   - lat_long_labeled                   — "Lat X, Long Y" form (GPS Map Camera)
#   - *_inferred_no_hemi                 — Paddle truncated trailing E/W; lat
#                                          parsed cleanly on same line, value
#                                          validated against Austria bbox
CLEAN_FORMATS = {
    "dms",
    "decimal",
    "dms_min_sec_joined",
    "lat_long_labeled",
    "decimal_inferred_no_hemi",
    "dms_inferred_no_hemi",
    "dms_min_sec_joined_inferred_no_hemi",
}
# Rescue formats: parse only succeeded with permissive heuristics. LOW flag.
RESCUE_FORMATS = {
    "dms_digit_misread",
    "dms_fully_joined",
    "dms_tolerant",
    "decimal_space_inferred_no_hemi",  # space-as-decimal, guess-y
    # Hemisphere inferred from Austria bbox range (no N/S/E/W in OCR):
    "dms_inferred_from_range",
    "dms_min_sec_joined_inferred_from_range",
    "dms_space_decimal_inferred_from_range",
}
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
    hemi = ("N", "S")[value < 0] if hemi_axis == "lat" else ("E", "W")[value < 0]
    value = abs(value)
    deg = int(value)
    minutes_full = (value - deg) * 60
    minutes = int(minutes_full)
    seconds = round((minutes_full - minutes) * 60, 5)
    return f"{deg}°{minutes}'{seconds}\"{hemi}"


def _run_apple_vision_fallback(image_path: Path) -> list[tuple[str, float]] | None:
    """Run Apple Vision OCR via ocrmac. Returns the same shape as run_paddle:
    list of (text, confidence). Returns None on any import or runtime failure
    so callers can degrade gracefully on non-mac platforms.
    """
    try:
        from ocrmac import ocrmac
    except ImportError:
        return None
    try:
        annotations = ocrmac.OCR(
            str(image_path),
            recognition_level="accurate",
            language_preference=["de-DE", "en-US"],
        ).recognize()
    except Exception:  # noqa: BLE001
        return None
    return [(text, float(conf)) for text, conf, _bbox in annotations]


def build_paddle_ocr(lang: str = "german"):
    from paddleocr import PaddleOCR

    mobile_models = {
        "text_detection_model_name": "PP-OCRv5_mobile_det",
        "text_recognition_model_name": "latin_PP-OCRv5_mobile_rec",
    }
    for kwargs in (
        {**mobile_models, "lang": lang, "use_textline_orientation": True},
        {**mobile_models, "lang": lang},
        {"lang": lang},
    ):
        try:
            return PaddleOCR(**kwargs)
        except (TypeError, ValueError):
            continue
    return PaddleOCR(lang=lang)


def run_paddle(ocr, band: Image.Image) -> list[tuple[str, float]]:
    """Run PaddleOCR on a band image. Returns list of (text, confidence).

    Handles both predict (v3.x) and ocr (v2.x) APIs.
    """
    arr = np.array(band.convert("RGB"))
    results: list[tuple[str, float]] = []
    if hasattr(ocr, "predict"):
        preds = ocr.predict(arr)
        for pred in preds:
            if isinstance(pred, dict):
                texts = pred.get("rec_texts", []) or pred.get("rec_text", [])
                scores = pred.get("rec_scores", []) or pred.get("rec_score", [])
                for text, conf in zip(texts, scores):
                    results.append((text, float(conf)))
            else:
                for line in pred:
                    if not line:
                        continue
                    _bbox, (text, conf) = line[0], line[1]
                    results.append((text, float(conf)))
    else:
        preds = ocr.ocr(arr)
        if preds and preds[0]:
            for line in preds[0]:
                if not line:
                    continue
                _bbox, (text, conf) = line
                results.append((text, float(conf)))
    return results


def score_one_coord(coord: dict, ocr_conf: float, conf_threshold: float) -> tuple[str, str]:
    """Decide HIGH/LOW for a single parsed coordinate."""
    fmt = coord["format"]
    raw = coord["raw"]

    if fmt in RESCUE_FORMATS:
        return "LOW", f"rescue_pattern_used:{fmt}"

    if fmt == "dms" and "°" not in raw:
        return "LOW", "dms_format_without_real_degree_sign"

    if ocr_conf < conf_threshold:
        return "LOW", f"ocr_confidence_{ocr_conf:.3f}_below_{conf_threshold}"

    return "HIGH", "all_criteria_met"


def enrich(coord: dict, axis: str, ocr_conf: float, conf_threshold: float) -> dict:
    flag, reason = score_one_coord(coord, ocr_conf, conf_threshold)
    return {
        "decimal": coord["value"],
        "dms": decimal_to_dms(coord["value"], axis),
        "raw_ocr": coord["raw"],
        "format": coord["format"],
        "ocr_confidence": round(ocr_conf, 4),
        "flag": flag,
        "flag_reason": reason,
    }


def best_candidates_from_lines(
    detections: list[tuple[str, float]],
) -> tuple[dict | None, dict | None, float, float]:
    """For each OCR line, try parse_coordinates. Track best lat and best lon
    (by OCR confidence) across all lines. Returns (lat_coord, lon_coord,
    lat_conf, lon_conf).
    """
    best_lat: dict | None = None
    best_lon: dict | None = None
    best_lat_conf = -1.0
    best_lon_conf = -1.0

    for text, conf in detections:
        try:
            parsed = parse_coordinates(text)
        except StrictDmsError:
            continue
        valid = validate_austria(parsed)
        if "lat" in valid and conf > best_lat_conf:
            best_lat = valid["lat"]
            best_lat_conf = conf
        if "lon" in valid and conf > best_lon_conf:
            best_lon = valid["lon"]
            best_lon_conf = conf

    # Also try joined text per band as fallback — sometimes coord is split
    # across detections that Paddle decided to box separately. In that case
    # use min of the two confidences as conservative.
    joined = " ".join(t for t, _ in detections)
    if joined.strip():
        try:
            parsed = parse_coordinates(joined)
        except StrictDmsError:
            parsed = {}
        valid = validate_austria(parsed)
        if best_lat is None and "lat" in valid:
            best_lat = valid["lat"]
            best_lat_conf = min((c for _, c in detections), default=0.0)
        if best_lon is None and "lon" in valid:
            best_lon = valid["lon"]
            best_lon_conf = min((c for _, c in detections), default=0.0)

    return best_lat, best_lon, best_lat_conf, best_lon_conf


_FRAC_RE = re.compile(r"[.,](\d+)(?:[\"″]?[NSEW]?)\s*$")


def count_frac_digits(raw: str) -> int | None:
    """Count decimal digits AFTER the last . or , in a raw OCR string.
    Returns None if no fraction found (integer-only, e.g., '46N')."""
    if not raw:
        return None
    m = _FRAC_RE.search(raw)
    if m:
        return len(m.group(1))
    return None


def overall_flag(lat_flag: str | None, lon_flag: str | None) -> str:
    """Aggregate per-coord flags into a record-level flag."""
    if lat_flag is None and lon_flag is None:
        return "NO_GPS"
    if lat_flag is None or lon_flag is None:
        return "GPS_LOW"  # one coord missing
    if lat_flag == "HIGH" and lon_flag == "HIGH":
        return "GPS_HIGH"
    return "GPS_LOW"


def check_precision_asymmetry(lat_raw: str | None, lon_raw: str | None, threshold: int = 3) -> str | None:
    """Detect OCR-truncation by comparing fractional digit counts between lat
    and lon raw OCR strings. Returns a reason string if asymmetric (caller
    should downgrade), else None.

    A real watermark normally writes lat and lon with the same precision. A
    large difference (≥3) strongly suggests OCR truncated one of them.
    """
    if lat_raw is None or lon_raw is None:
        return None
    lat_f = count_frac_digits(lat_raw)
    lon_f = count_frac_digits(lon_raw)
    if lat_f is None or lon_f is None:
        return None
    if abs(lat_f - lon_f) >= threshold:
        return f"precision_asymmetry:lat_frac={lat_f}_lon_frac={lon_f}"
    return None


def process_image(
    image_path: Path,
    ocr,
    conf_threshold: float,
    use_gemini: bool,
) -> tuple[dict, str, bool]:
    """Run the full GPS-extraction pipeline on a single image.

    Returns ``(result, record_flag, gemini_used)``. ``result`` has the same
    shape that's written to per-image JSON files in directory mode (image /
    source_path / engine / ocr_conf_threshold / overall_flag / gps / bands /
    validation_bbox_austria / processed_at).
    """
    with Image.open(image_path) as raw:
        img = raw.convert("RGB")
        bands = crop_bands(img)

    band_results: dict[str, dict] = {}
    for band_name, band_img in bands.items():
        detections = run_paddle(ocr, band_img)
        lat, lon, lat_conf, lon_conf = best_candidates_from_lines(detections)
        band_results[band_name] = {
            "detections": [{"text": t, "ocr_confidence": round(c, 4)} for t, c in detections],
            "candidate_lat": lat,
            "candidate_lon": lon,
            "candidate_lat_conf": lat_conf if lat_conf >= 0 else None,
            "candidate_lon_conf": lon_conf if lon_conf >= 0 else None,
        }

    best_lat = None
    best_lon = None
    best_lat_conf = -1.0
    best_lon_conf = -1.0
    best_lat_band = None
    best_lon_band = None
    for band_name, br in band_results.items():
        if br["candidate_lat"] is not None and br["candidate_lat_conf"] > best_lat_conf:
            best_lat = br["candidate_lat"]
            best_lat_conf = br["candidate_lat_conf"]
            best_lat_band = band_name
        if br["candidate_lon"] is not None and br["candidate_lon_conf"] > best_lon_conf:
            best_lon = br["candidate_lon"]
            best_lon_conf = br["candidate_lon_conf"]
            best_lon_band = band_name

    # Fallback 1: bands extracted nothing → try OCR on the full image.
    if best_lat is None and best_lon is None:
        full_detections = run_paddle(ocr, img)
        lat_f, lon_f, lat_conf_f, lon_conf_f = best_candidates_from_lines(full_detections)
        band_results["full_image_fallback"] = {
            "detections": [{"text": t, "ocr_confidence": round(c, 4)} for t, c in full_detections],
            "candidate_lat": lat_f,
            "candidate_lon": lon_f,
            "candidate_lat_conf": lat_conf_f if lat_conf_f >= 0 else None,
            "candidate_lon_conf": lon_conf_f if lon_conf_f >= 0 else None,
        }
        if lat_f is not None:
            best_lat, best_lat_conf, best_lat_band = lat_f, lat_conf_f, "full_image_fallback"
        if lon_f is not None:
            best_lon, best_lon_conf, best_lon_band = lon_f, lon_conf_f, "full_image_fallback"

    # Fallback 2: still nothing → Apple Vision on full image (macOS-only).
    if best_lat is None and best_lon is None:
        apple_detections = _run_apple_vision_fallback(image_path)
        if apple_detections is not None:
            lat_a, lon_a, lat_conf_a, lon_conf_a = best_candidates_from_lines(apple_detections)
            band_results["apple_vision_fallback"] = {
                "detections": [{"text": t, "ocr_confidence": round(c, 4)} for t, c in apple_detections],
                "candidate_lat": lat_a,
                "candidate_lon": lon_a,
                "candidate_lat_conf": lat_conf_a if lat_conf_a >= 0 else None,
                "candidate_lon_conf": lon_conf_a if lon_conf_a >= 0 else None,
            }
            if lat_a is not None:
                best_lat, best_lat_conf, best_lat_band = lat_a, lat_conf_a, "apple_vision_fallback"
            if lon_a is not None:
                best_lon, best_lon_conf, best_lon_band = lon_a, lon_conf_a, "apple_vision_fallback"

    gps: dict = {}
    lat_flag = None
    lon_flag = None
    if best_lat is not None:
        gps["lat"] = enrich(best_lat, "lat", best_lat_conf, conf_threshold)
        gps["lat"]["source_band"] = best_lat_band
        lat_flag = gps["lat"]["flag"]
    if best_lon is not None:
        gps["lon"] = enrich(best_lon, "lon", best_lon_conf, conf_threshold)
        gps["lon"]["source_band"] = best_lon_band
        lon_flag = gps["lon"]["flag"]

    if "lat" in gps and "lon" in gps:
        asym_reason = check_precision_asymmetry(
            gps["lat"].get("raw_ocr"),
            gps["lon"].get("raw_ocr"),
        )
        if asym_reason:
            gps["lat"]["flag"] = "LOW"
            gps["lat"]["flag_reason"] = asym_reason
            gps["lon"]["flag"] = "LOW"
            gps["lon"]["flag_reason"] = asym_reason
            lat_flag = "LOW"
            lon_flag = "LOW"

    record_flag = overall_flag(lat_flag, lon_flag)

    # Fallback 3: Gemini Vision LLM. Triggered when overall_flag is LOW or
    # NO_GPS. Per axis: fill missing slots, upgrade LOW→HIGH if Gemini is
    # HIGH, otherwise leave the OCR-derived value alone.
    gemini_used = False
    if use_gemini and record_flag in ("GPS_LOW", "NO_GPS"):
        try:
            gemini_std, gemini_raw = run_gemini_fallback(image_path)
        except GeminiFallbackError as exc:
            band_results["gemini_vision_fallback"] = {"error": str(exc)}
        else:
            band_results["gemini_vision_fallback"] = {
                "raw_response": gemini_raw,
                "candidate_lat": gemini_std.get("lat"),
                "candidate_lon": gemini_std.get("lon"),
            }
            for axis in ("lat", "lon"):
                new = gemini_std.get(axis)
                if new is None:
                    continue
                existing = gps.get(axis)
                if existing is None:
                    gps[axis] = new
                    gemini_used = True
                elif existing.get("flag") == "LOW" and new["flag"] == "HIGH":
                    gps[axis] = new
                    gemini_used = True
            if gemini_used:
                lat_flag = gps.get("lat", {}).get("flag")
                lon_flag = gps.get("lon", {}).get("flag")
                record_flag = overall_flag(lat_flag, lon_flag)

    result = {
        "image": image_path.name,
        "source_path": str(image_path),
        "engine": "paddleocr_v5_mobile",
        "ocr_conf_threshold": conf_threshold,
        "overall_flag": record_flag,
        "gps": gps,
        "bands": band_results,
        "validation_bbox_austria": {"lat": list(AUSTRIA_LAT), "lon": list(AUSTRIA_LON)},
        "processed_at": datetime.now(timezone.utc).isoformat(),
    }
    return result, record_flag, gemini_used


def resolve_image_path(image_name: str, source: Path) -> Path | None:
    """Resolve a record's ``image_name`` to an actual file path.

    Tries in order: absolute path → ``base / image_name`` → recursive search
    under ``base`` (where ``base`` is ``source`` if a directory, else its
    parent). Returns ``None`` if no match.
    """
    p = Path(image_name)
    if p.is_absolute():
        return p if p.exists() else None
    base = source if source.is_dir() else source.parent
    direct = base / image_name
    if direct.exists():
        return direct
    for candidate in base.rglob(image_name):
        if candidate.is_file():
            return candidate
    return None


def run_json_mode(args, ocr, source_root: Path) -> int:
    """Pipeline driver for ``--input-json``: read records, augment lat/lon.

    Input is a JSON object or array of objects with the shape::

        {"id": 666, "image_name": "4 (2).jpg", "category": 3,
         "latitude": 0, "longitude": 0, "confidence": 0.89, "status": "created"}

    The output mirrors the input exactly: only ``latitude`` and ``longitude``
    are overwritten when GPS extraction succeeds. All other keys pass through
    unchanged. The detailed per-image debug JSON is still written to
    ``args.out`` for traceability.
    """
    raw_input = json.loads(Path(args.input_json).read_text(encoding="utf-8"))
    records = raw_input if isinstance(raw_input, list) else [raw_input]
    is_list = isinstance(raw_input, list)

    args.out.mkdir(parents=True, exist_ok=True)
    summary = {"GPS_HIGH": 0, "GPS_LOW": 0, "NO_GPS": 0}
    failures = 0
    augmented: list[dict] = []

    for idx, rec in enumerate(records, 1):
        out_rec = dict(rec)
        image_name = rec.get("image_name")
        if not image_name:
            print(f"[{idx}/{len(records)}] SKIP (no image_name)", file=sys.stderr)
            augmented.append(out_rec)
            continue
        image_path = resolve_image_path(image_name, args.source)
        if image_path is None:
            print(
                f"[{idx}/{len(records)}] SKIP {image_name} (not found under {args.source})",
                file=sys.stderr,
            )
            augmented.append(out_rec)
            continue

        stem = output_stem(image_path, source_root)
        print(f"[{idx}/{len(records)}] {stem} ... ", end="", flush=True, file=sys.stderr)
        try:
            result, record_flag, gemini_used = process_image(
                image_path, ocr, args.conf_threshold, args.gemini_fallback
            )
            summary[record_flag] += 1
            (args.out / f"{stem}.json").write_text(
                json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            lat_v = result["gps"].get("lat", {}).get("decimal")
            lon_v = result["gps"].get("lon", {}).get("decimal")
            if lat_v is not None:
                out_rec["latitude"] = lat_v
            if lon_v is not None:
                out_rec["longitude"] = lon_v
            tag = " [gemini]" if gemini_used else ""
            print(f"{record_flag:8s} lat={lat_v} lon={lon_v}{tag}", file=sys.stderr)
        except Exception as exc:  # noqa: BLE001
            failures += 1
            print(f"FAILED: {exc}", file=sys.stderr)
        augmented.append(out_rec)

    out_data = augmented if is_list else augmented[0]
    serialized = json.dumps(out_data, ensure_ascii=False, indent=2)
    if args.output_json and str(args.output_json) != "-":
        Path(args.output_json).write_text(serialized, encoding="utf-8")
        print(f"Wrote augmented JSON to {args.output_json}", file=sys.stderr)
    else:
        sys.stdout.write(serialized + "\n")

    print(f"Flag summary: {summary}", file=sys.stderr)
    return 0 if failures == 0 else 2


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--lang", default="german")
    parser.add_argument("--conf-threshold", type=float, default=DEFAULT_OCR_THRESHOLD,
                        help="OCR confidence threshold for HIGH flag (default 0.90).")
    parser.add_argument("--gemini-fallback", dest="gemini_fallback", action="store_true", default=True,
                        help="On GPS_LOW / NO_GPS, ask Google Gemini to read the watermark (default on).")
    parser.add_argument("--no-gemini-fallback", dest="gemini_fallback", action="store_false",
                        help="Disable the Gemini Vision fallback.")
    parser.add_argument("--input-json", type=Path, default=None,
                        help="Path to a JSON file (object or array) of records of shape "
                             "{id, image_name, category, latitude, longitude, confidence, status}. "
                             "Each record's latitude/longitude is filled in from the image's GPS watermark; "
                             "all other fields pass through unchanged.")
    parser.add_argument("--output-json", default=None,
                        help="Where to write augmented records. Use '-' or omit for stdout. "
                             "Only meaningful with --input-json.")
    args = parser.parse_args()

    try:
        import paddleocr  # noqa: F401
    except ImportError:
        print("ERROR: paddleocr not installed. pip install paddlepaddle paddleocr", file=sys.stderr)
        return 1

    args.out.mkdir(parents=True, exist_ok=True)
    source_root = args.source if args.source.is_dir() else args.source.parent

    print(f"Engine:    PaddleOCR PP-OCRv5 mobile  lang={args.lang}", file=sys.stderr)
    print(f"Source:    {args.source}", file=sys.stderr)
    print(f"Out:       {args.out}", file=sys.stderr)
    print(f"Threshold: OCR conf >= {args.conf_threshold} for HIGH flag", file=sys.stderr)
    print(
        f"Gemini:    {'on (fallback for GPS_LOW / NO_GPS)' if args.gemini_fallback else 'off'}",
        file=sys.stderr,
    )
    print("Loading PaddleOCR (first run downloads weights)...", file=sys.stderr)
    ocr = build_paddle_ocr(args.lang)
    print("Reader ready.\n", file=sys.stderr)

    if args.input_json is not None:
        return run_json_mode(args, ocr, source_root)

    # Directory mode (legacy): iterate every image under --source.
    images = iter_images(args.source)
    if not images:
        print(f"No images in {args.source}", file=sys.stderr)
        return 1
    if args.limit and args.limit > 0:
        images = images[: args.limit]

    print(f"Images:    {len(images)}")

    failures = 0
    summary = {"GPS_HIGH": 0, "GPS_LOW": 0, "NO_GPS": 0}

    for idx, image_path in enumerate(images, 1):
        stem = output_stem(image_path, source_root)
        print(f"[{idx}/{len(images)}] {stem} ... ", end="", flush=True)
        try:
            result, record_flag, gemini_used = process_image(
                image_path, ocr, args.conf_threshold, args.gemini_fallback
            )
            summary[record_flag] += 1
            out_path = args.out / f"{stem}.json"
            out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            lat_v = result["gps"].get("lat", {}).get("decimal")
            lon_v = result["gps"].get("lon", {}).get("decimal")
            tag = " [gemini]" if gemini_used else ""
            print(f"{record_flag:8s} lat={lat_v} lon={lon_v}{tag}")
        except Exception as exc:  # noqa: BLE001
            failures += 1
            print(f"FAILED: {exc}")

    print(f"\nDone. Success: {len(images) - failures}, Failed: {failures}")
    print(f"Flag summary: {summary}")
    return 0 if failures == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())

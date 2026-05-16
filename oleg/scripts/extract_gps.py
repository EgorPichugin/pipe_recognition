#!/usr/bin/env python3
"""Extract GPS coordinates from watermark on construction-site photos.

Strategy:
1. Crop top and bottom bands (full width, 40% height each). The watermark
   sits in one of them regardless of which corner the camera app placed it.
2. Upscale each band 2x so OCR sees more pixels per glyph — fine marks like
   ``°`` and ``'`` survive recognition far better at 2x.
3. Run EasyOCR with a character allowlist restricted to GPS symbols. The
   model physically cannot output ``*`` or ``9`` in place of ``°`` because
   those characters are filtered out of the allowed set.
4. Regex-parse for DMS or decimal coordinate patterns.
5. Validate against Austria coordinate range to drop OCR false positives.

Writes one JSON per image to ``out/gps/<stem>.json`` with the parsed
coordinates plus the raw OCR text per band for debugging.
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
DEFAULT_OUT = REPO_ROOT / "out" / "gps"
DEFAULT_LIMIT = 5

GPS_ALLOWLIST = "0123456789°'\"NSEW.,± m"
BAND_HEIGHT_FRAC = 0.40
UPSCALE = 2.0

# Austria bounding box (a bit padded)
AUSTRIA_LAT = (46.0, 49.5)
AUSTRIA_LON = (9.0, 17.5)

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}

# DMS with proper or *,o degree symbol — e.g. "46°33'56.238\"N", "46*33 66,238\"N"
DMS_RE = re.compile(
    r"(\d{1,3})\s*[°*o]\s*(\d{1,2})\s*['′\s]\s*(\d{1,2})\s*[.,]\s*(\d+)\s*[\"″]?\s*([NSEW])",
    re.IGNORECASE,
)
# DMS where degree symbol was misread as a digit (e.g. 14°17 -> 14917).
# 2-digit deg + 1 stray digit (the misread °) + 2-digit min + apostrophe/space
# + 2-digit sec + decimal + fraction + hemi. The (?<!\d) lookbehind keeps the
# pattern from grabbing the middle of an arbitrary digit run like a phone.
DMS_DIGIT_RE = re.compile(
    r"(?<!\d)(\d{2})\d(\d{2})\s*['′\s]\s*(\d{1,2})\s*[.,]\s*(\d+)\s*[\"″]?\s*([NSEW])",
    re.IGNORECASE,
)
# DMS fully joined — both ° and ' replaced by digit/nothing. E.g. "1491717,08285E"
# = 14°17'17,08285"E. 2-digit deg + 1 stray digit (°) + 2-digit min + 2-digit sec.
DMS_FULLY_JOINED_RE = re.compile(
    r"(?<!\d)(\d{2})\d(\d{2})(\d{2})\s*[.,]\s*(\d+)\s*[\"″]?\s*([NSEW])",
    re.IGNORECASE,
)
# DMS with proper ° but min and sec are joined together with no separator.
# E.g. "14°1723,58729\"E" = 14°17'23,58729"E (apostrophe between min and sec missing).
# Clean enough to count as a HIGH-eligible format: 4 digits after ° split
# unambiguously as (min=2, sec_int=2).
DMS_MIN_SEC_JOINED_RE = re.compile(
    r"(\d{1,3})\s*[°*o:]\s*(\d{2})(\d{2})\s*[.,]\s*(\d+)\s*[\"″]?\s*([NSEW])",
    re.IGNORECASE,
)
# Decimal degrees — e.g. "46.56584134N"
DECIMAL_RE = re.compile(
    r"(\d{1,3})\s*[.,]\s*(\d{4,})\s*([NSEW])",
    re.IGNORECASE,
)
# "Lat 46.552538, Long 14.291943" — format used by GPS Map Camera app.
# Captures both coords in one go; hemisphere is implied (positive = N/E).
LAT_LONG_LABELED_RE = re.compile(
    r"Lat\s*[:=]?\s*(-?\d{1,3}[.,]\d+)\s*[,\s]+\s*Long\s*[:=]?\s*(-?\d{1,3}[.,]\d+)",
    re.IGNORECASE,
)
# Tolerant DMS — allows any 1-3 non-digit, non-NSEW chars as separator between
# deg/min/sec. Catches "46.33 52,67045\"N" (dot for °) and "14 17i27 ,492E"
# (space for °, letter i for '). Last in priority because it's the most
# permissive — strict patterns above take precedence via setdefault().
DMS_TOLERANT_RE = re.compile(
    r"(\d{1,3})[^\d\nNSEW]{1,3}(\d{1,2})[^\d\nNSEW]{1,3}(\d{1,2})\s*[.,]\s*(\d+)\s*[^\dNSEW\n]{0,3}([NSEW])",
    re.IGNORECASE,
)

# === No-hemisphere variants for inference (lon recovery when Paddle truncated E/W) ===
# These run ONLY when we already parsed lat on the same line, so the resulting
# "no-hemi" lon match is strongly contextualised. Validation against Austria
# bounding box is the final safety net.
DECIMAL_NO_HEMI_RE = re.compile(
    r"(?<!\d)(\d{1,3})\s*[.,]\s*(\d{4,})(?!\d)",
)
DMS_NO_HEMI_RE = re.compile(
    r"(?<!\d)(\d{1,3})\s*[°*o:]\s*(\d{1,2})\s*['′\s]\s*(\d{1,2})\s*[.,]\s*(\d+)\s*[\"″]?(?!\d)",
)
DMS_MIN_SEC_JOINED_NO_HEMI_RE = re.compile(
    r"(?<!\d)(\d{1,3})\s*[°*o:]\s*(\d{2})(\d{2})\s*[.,]\s*(\d+)\s*[\"″]?(?!\d)",
)
# Space-as-decimal (OCR ate the `.` between deg and frac): "14 28969".
# Riskier — only used in inference mode after a confirmed lat on the same line.
DECIMAL_SPACE_NO_HEMI_RE = re.compile(
    r"(?<!\d)(\d{1,3})\s+(\d{4,})(?!\d)",
)
# Full DMS where the comma between sec_int and fraction got eaten and replaced
# by a space: "14°17'49 5283" → 14°17'49.5283".
DMS_SPACE_DECIMAL_NO_HEMI_RE = re.compile(
    r"(?<!\d)(\d{1,3})\s*[°*o:]\s*(\d{1,2})\s*['′\s]\s*(\d{1,2})\s+(\d{2,})\s*[\"″]?(?!\d)",
)


class StrictDmsError(ValueError):
    """Raised when DMS math validity fails (min>=60 or sec>=60)."""


def dms_to_decimal(deg: str, minutes: str, sec_int: str, sec_frac: str, hemi: str) -> float:
    minutes_int = int(minutes)
    seconds = float(f"{sec_int}.{sec_frac}")
    if minutes_int >= 60:
        raise StrictDmsError(f"minutes >= 60: {minutes_int}")
    if seconds >= 60:
        raise StrictDmsError(f"seconds >= 60: {seconds}")
    val = int(deg) + minutes_int / 60 + seconds / 3600
    if hemi.upper() in ("S", "W"):
        val = -val
    return round(val, 10)


def parse_coordinates(text: str) -> dict:
    found: dict[str, dict] = {}
    lat_match_end: int | None = None
    lon_match_start: int | None = None

    def store(key: str, payload: dict, end_idx: int | None = None, start_idx: int | None = None) -> None:
        nonlocal lat_match_end, lon_match_start
        if key not in found:
            found[key] = payload
            if key == "lat" and end_idx is not None and lat_match_end is None:
                lat_match_end = end_idx
            if key == "lon" and start_idx is not None and lon_match_start is None:
                lon_match_start = start_idx

    # 'Lat X, Long Y' form (single-shot, parses both at once).
    for m in LAT_LONG_LABELED_RE.finditer(text):
        lat_raw, lon_raw = m.group(1), m.group(2)
        try:
            lat_val = float(lat_raw.replace(",", "."))
            lon_val = float(lon_raw.replace(",", "."))
        except ValueError:
            continue
        store("lat", {"value": round(lat_val, 10), "raw": f"Lat {lat_raw}", "format": "lat_long_labeled"}, m.end(1))
        store("lon", {"value": round(lon_val, 10), "raw": f"Long {lon_raw}", "format": "lat_long_labeled"}, end_idx=m.end(2), start_idx=m.start(2))

    for m in DMS_RE.finditer(text):
        deg, minutes, sec_int, sec_frac, hemi = m.groups()
        try:
            val = dms_to_decimal(deg, minutes, sec_int, sec_frac, hemi)
        except (ValueError, ZeroDivisionError):
            continue
        key = "lat" if hemi.upper() in ("N", "S") else "lon"
        store(key, {"value": val, "raw": m.group(0).strip(), "format": "dms"}, m.end(), m.start())

    for m in DMS_MIN_SEC_JOINED_RE.finditer(text):
        deg, minutes, sec_int, sec_frac, hemi = m.groups()
        try:
            val = dms_to_decimal(deg, minutes, sec_int, sec_frac, hemi)
        except (ValueError, ZeroDivisionError):
            continue
        key = "lat" if hemi.upper() in ("N", "S") else "lon"
        store(key, {"value": val, "raw": m.group(0).strip(), "format": "dms_min_sec_joined"}, m.end(), m.start())

    for m in DMS_DIGIT_RE.finditer(text):
        deg, minutes, sec_int, sec_frac, hemi = m.groups()
        try:
            val = dms_to_decimal(deg, minutes, sec_int, sec_frac, hemi)
        except (ValueError, ZeroDivisionError):
            continue
        key = "lat" if hemi.upper() in ("N", "S") else "lon"
        store(key, {"value": val, "raw": m.group(0).strip(), "format": "dms_digit_misread"}, m.end(), m.start())

    for m in DMS_FULLY_JOINED_RE.finditer(text):
        deg, minutes, sec_int, sec_frac, hemi = m.groups()
        try:
            val = dms_to_decimal(deg, minutes, sec_int, sec_frac, hemi)
        except (ValueError, ZeroDivisionError):
            continue
        key = "lat" if hemi.upper() in ("N", "S") else "lon"
        store(key, {"value": val, "raw": m.group(0).strip(), "format": "dms_fully_joined"}, m.end(), m.start())

    for m in DECIMAL_RE.finditer(text):
        deg, frac, hemi = m.groups()
        try:
            val = float(f"{deg}.{frac}")
        except ValueError:
            continue
        if hemi.upper() in ("S", "W"):
            val = -val
        val = round(val, 10)
        key = "lat" if hemi.upper() in ("N", "S") else "lon"
        store(key, {"value": val, "raw": m.group(0).strip(), "format": "decimal"}, m.end(), m.start())

    for m in DMS_TOLERANT_RE.finditer(text):
        deg, minutes, sec_int, sec_frac, hemi = m.groups()
        try:
            val = dms_to_decimal(deg, minutes, sec_int, sec_frac, hemi)
        except (ValueError, ZeroDivisionError):
            continue
        key = "lat" if hemi.upper() in ("N", "S") else "lon"
        store(key, {"value": val, "raw": m.group(0).strip(), "format": "dms_tolerant"}, m.end(), m.start())

    # Inference: if we got lat but lon is missing, look in the text AFTER the
    # lat match for a coord-shaped chunk without trailing N/S/E/W. Common in
    # Paddle output where the bounding box truncates just before the final 'E'.
    # Inferred lon is assumed E because Austrian sites are always east of
    # Greenwich; we still validate against the lon bbox before accepting.
    if "lat" in found and "lon" not in found and lat_match_end is not None:
        _try_infer_lon(text[lat_match_end:], found)

    # Reverse inference: lon parsed but lat missing — look BEFORE the lon match.
    # Inferred lat is assumed N (Austria is always north of equator).
    if "lon" in found and "lat" not in found and lon_match_start is not None:
        _try_infer_lat(text[:lon_match_start], found)

    # Range-based standalone inference: when neither lat nor lon was anchored
    # via a hemisphere letter, scan for coord-shaped chunks anywhere in text
    # and classify each by which Austria bbox range it falls in.
    if "lat" not in found or "lon" not in found:
        _try_infer_from_range(text, found)

    return found


def _try_infer_lon(tail: str, found: dict) -> None:
    """Mutate ``found`` to add an inferred lon (hemisphere E) if one of the
    no-hemi patterns matches in ``tail`` and the value falls in Austria.
    """
    candidates: list[tuple] = []  # (regex, format_label, groups_handler)

    def decimal_handler(m):
        deg, frac = m.group(1), m.group(2)
        try:
            return float(f"{deg}.{frac}")
        except ValueError:
            return None

    def dms_handler(m):
        try:
            return dms_to_decimal(m.group(1), m.group(2), m.group(3), m.group(4), "E")
        except (ValueError, ZeroDivisionError):
            return None

    def dms_min_sec_joined_handler(m):
        try:
            return dms_to_decimal(m.group(1), m.group(2), m.group(3), m.group(4), "E")
        except (ValueError, ZeroDivisionError):
            return None

    # Order matters: DMS variants must be tried FIRST. Otherwise the sec,frac
    # tail of a partial DMS like "14°17'17,24028\"" gets matched by decimal as
    # "17,24028" — that lies inside the Austria lon range and produces a
    # silently wrong lon. Trying DMS first means we consume the whole
    # "14°17'17,24028" as one unit and compute the right 14.288… value.
    candidates.append((DMS_NO_HEMI_RE, "dms_inferred_no_hemi", dms_handler))
    candidates.append((DMS_MIN_SEC_JOINED_NO_HEMI_RE, "dms_min_sec_joined_inferred_no_hemi", dms_min_sec_joined_handler))
    candidates.append((DECIMAL_NO_HEMI_RE, "decimal_inferred_no_hemi", decimal_handler))
    candidates.append((DECIMAL_SPACE_NO_HEMI_RE, "decimal_space_inferred_no_hemi", decimal_handler))

    for regex, fmt, handler in candidates:
        for m in regex.finditer(tail):
            value = handler(m)
            if value is None:
                continue
            value = round(value, 10)
            if AUSTRIA_LON[0] <= value <= AUSTRIA_LON[1]:
                found["lon"] = {
                    "value": value,
                    "raw": m.group(0).strip(),
                    "format": fmt,
                }
                return


def _try_infer_from_range(text: str, found: dict) -> None:
    """Standalone hemi inference. Scan ``text`` for any DMS / decimal coord
    chunks without a hemisphere letter and classify each by which Austria
    bbox range its decimal value falls in.

    Used when the regular hemisphere-anchored patterns missed the watermark
    entirely (e.g. OCR garbled the trailing N/E or it sits in a separate
    detection box from the digits). All inferred results are RESCUE-tier
    (LOW flag) — Austria range is narrow enough that false positives are
    rare, but they can happen.
    """
    def decimal_handler(m):
        try:
            return float(f"{m.group(1)}.{m.group(2)}")
        except ValueError:
            return None

    def dms_handler(m):
        try:
            return dms_to_decimal(m.group(1), m.group(2), m.group(3), m.group(4), "N")
        except (ValueError, ZeroDivisionError):
            return None

    # NOTE: DECIMAL_NO_HEMI_RE intentionally NOT in this list. Without a partner
    # coord to anchor the search, it matches Austrian dates like "10.2024"
    # (year part) and addresses like "9, 9161 Maria Rain" — both fall inside
    # the Austria lon range and would produce false positives. DMS-based no-hemi
    # regexes require a ``°`` (or ``*`` / ``:`` substitute), which dates and
    # addresses don't carry, so they stay safe.
    candidates: list[tuple] = [
        (DMS_NO_HEMI_RE, "dms_inferred_from_range", dms_handler),
        (DMS_MIN_SEC_JOINED_NO_HEMI_RE, "dms_min_sec_joined_inferred_from_range", dms_handler),
        (DMS_SPACE_DECIMAL_NO_HEMI_RE, "dms_space_decimal_inferred_from_range", dms_handler),
    ]

    for regex, fmt, handler in candidates:
        for m in regex.finditer(text):
            value = handler(m)
            if value is None:
                continue
            value = round(value, 10)
            if "lat" not in found and AUSTRIA_LAT[0] <= value <= AUSTRIA_LAT[1]:
                found["lat"] = {
                    "value": value,
                    "raw": m.group(0).strip(),
                    "format": fmt,
                }
                continue
            if "lon" not in found and AUSTRIA_LON[0] <= value <= AUSTRIA_LON[1]:
                found["lon"] = {
                    "value": value,
                    "raw": m.group(0).strip(),
                    "format": fmt,
                }


def _try_infer_lat(head: str, found: dict) -> None:
    """Mutate ``found`` to add an inferred lat (hemisphere N) by scanning the
    text BEFORE a confirmed lon match. We pick the LAST match in ``head``
    (closest to the lon) on the assumption it's lat for the same coord pair.
    """
    def decimal_handler(m):
        deg, frac = m.group(1), m.group(2)
        try:
            return float(f"{deg}.{frac}")
        except ValueError:
            return None

    def dms_handler(m):
        try:
            return dms_to_decimal(m.group(1), m.group(2), m.group(3), m.group(4), "N")
        except (ValueError, ZeroDivisionError):
            return None

    def dms_min_sec_joined_handler(m):
        try:
            return dms_to_decimal(m.group(1), m.group(2), m.group(3), m.group(4), "N")
        except (ValueError, ZeroDivisionError):
            return None

    # DMS-first ordering (see _try_infer_lon for the same rationale).
    candidates: list[tuple] = [
        (DMS_NO_HEMI_RE, "dms_inferred_no_hemi", dms_handler),
        (DMS_MIN_SEC_JOINED_NO_HEMI_RE, "dms_min_sec_joined_inferred_no_hemi", dms_min_sec_joined_handler),
        (DECIMAL_NO_HEMI_RE, "decimal_inferred_no_hemi", decimal_handler),
        (DECIMAL_SPACE_NO_HEMI_RE, "decimal_space_inferred_no_hemi", decimal_handler),
    ]

    for regex, fmt, handler in candidates:
        matches = list(regex.finditer(head))
        if not matches:
            continue
        # closest to the lon (last match) is most likely the lat for this pair
        for m in reversed(matches):
            value = handler(m)
            if value is None:
                continue
            value = round(value, 10)
            if AUSTRIA_LAT[0] <= value <= AUSTRIA_LAT[1]:
                found["lat"] = {
                    "value": value,
                    "raw": m.group(0).strip(),
                    "format": fmt,
                }
                return


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


def ocr_band(reader, band: Image.Image, use_allowlist: bool = False) -> list[tuple]:
    arr = np.array(band.convert("RGB"))
    if use_allowlist:
        return reader.readtext(arr, allowlist=GPS_ALLOWLIST)
    return reader.readtext(arr)


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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    parser.add_argument("--langs", default="de,en", help="EasyOCR languages.")
    parser.add_argument("--gpu", action="store_true")
    args = parser.parse_args()

    try:
        import easyocr
    except ImportError:
        print("ERROR: easyocr not installed. pip install easyocr", file=sys.stderr)
        return 1

    images = iter_images(args.source)
    if not images:
        print(f"No images in {args.source}", file=sys.stderr)
        return 1
    if args.limit and args.limit > 0:
        images = images[: args.limit]

    args.out.mkdir(parents=True, exist_ok=True)
    source_root = args.source if args.source.is_dir() else args.source.parent
    languages = [l.strip() for l in args.langs.split(",") if l.strip()]

    print(f"Loading EasyOCR reader (langs={languages})...")
    reader = easyocr.Reader(languages, gpu=args.gpu)
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
                upscaled = upscale(band_img)
                detections = ocr_band(reader, upscaled)
                texts = [d[1] for d in detections]
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

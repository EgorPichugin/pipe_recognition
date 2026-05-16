#!/usr/bin/env python3
"""Gemini Vision fallback for GPS watermark extraction.

Triggered by ``extract_gps_paddle_v2.py`` when PaddleOCR (and Apple Vision)
either parse nothing or only return a low-confidence read of the GPS Map
Camera watermark. The photo is sent to Google Gemini, which is asked to
read the coordinates directly off the visible watermark.

The LLM response is then mapped into the same coord-dict shape the rest
of the pipeline uses: ``decimal`` / ``dms`` / ``raw_ocr`` / ``format`` /
``ocr_confidence`` / ``flag`` / ``flag_reason`` / ``source_band``. So
callers can drop the result straight into ``gps["lat"]`` / ``gps["lon"]``
and emit the same JSON shape the OCR pipeline already produces.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from extract_gps import AUSTRIA_LAT, AUSTRIA_LON  # noqa: E402


GEMINI_PROMPT = """You are reading the GPS coordinate watermark stamped onto a construction-site photo by the "GPS Map Camera" mobile app. The watermark sits in a band along the top OR bottom edge of the image and shows latitude and longitude in either DMS form (e.g. 46°33'56,238"N  14°17'15,24"E) or decimal form (e.g. Lat 46.552538, Long 14.291943).

Read ONLY from the visible watermark — do not guess from any external knowledge of where the photo might be. If the watermark is missing, fully obscured, or unreadable, omit the corresponding key.

Return a single JSON object with this exact shape (omit lat or lon if unreadable):
{
  "lat": {
    "decimal": <number, positive for N, negative for S>,
    "raw": "<the exact substring you read for latitude, verbatim, including ° ' \" if present>",
    "hemisphere": "N" | "S",
    "confidence": "high" | "medium" | "low"
  },
  "lon": {
    "decimal": <number, positive for E, negative for W>,
    "raw": "<the exact substring you read for longitude, verbatim>",
    "hemisphere": "E" | "W",
    "confidence": "high" | "medium" | "low"
  },
  "notes": "<short note: which band held the watermark, was anything ambiguous?>"
}

Confidence rubric:
- "high"   = every digit and the hemisphere letter are unambiguous.
- "medium" = 1–2 digits ambiguous but bounded by context.
- "low"    = significant guesswork; multiple digits unclear.

Respond with the JSON object only. No prose, no markdown fences."""


CONFIDENCE_MAP = {
    "high": 0.95,
    "medium": 0.70,
    "low": 0.40,
}
FLAG_THRESHOLD = 0.85  # gemini "high" (0.95) → HIGH; anything below → LOW

_JSON_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


class GeminiFallbackError(RuntimeError):
    """Raised when the Gemini fallback can't run or the response is unusable."""


def _strip_json_fences(text: str) -> str:
    return _JSON_FENCE_RE.sub("", text).strip()


def _parse_json_response(text: str) -> dict:
    cleaned = _strip_json_fences(text)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(cleaned[start : end + 1])
        raise


def _ensure_dotenv_loaded() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")


def _decimal_to_dms(value: float, axis: str) -> str:
    hemi = ("N", "S")[value < 0] if axis == "lat" else ("E", "W")[value < 0]
    value = abs(value)
    deg = int(value)
    minutes_full = (value - deg) * 60
    minutes = int(minutes_full)
    seconds = round((minutes_full - minutes) * 60, 5)
    return f"{deg}°{minutes}'{seconds}\"{hemi}"


def call_gemini_vision(image_path: Path, model_name: str | None = None) -> dict[str, Any]:
    """Send ``image_path`` to Gemini Vision and return the parsed JSON dict.

    Raises ``GeminiFallbackError`` on missing key, missing SDK, network/API
    failure, or unparseable response.
    """
    _ensure_dotenv_loaded()
    # GEMINI_API_KEY is the per-developer key; LLM_KEY is the shared team-wide
    # fallback baked into other devs' envs, so a teammate without their own
    # Gemini key can still run the fallback.
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("LLM_KEY")
    if not api_key:
        raise GeminiFallbackError("Neither GEMINI_API_KEY nor LLM_KEY is configured.")

    try:
        import google.generativeai as genai
    except ImportError as exc:
        raise GeminiFallbackError("google-generativeai is not installed.") from exc

    model_name = model_name or os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_name)

    try:
        with Image.open(image_path) as raw:
            img = raw.convert("RGB")
            response = model.generate_content(
                [GEMINI_PROMPT, img],
                generation_config={
                    "response_mime_type": "application/json",
                    "temperature": 0.0,
                },
            )
    except Exception as exc:  # noqa: BLE001
        raise GeminiFallbackError(f"Gemini request failed: {exc}") from exc

    text = getattr(response, "text", None)
    if not text:
        raise GeminiFallbackError("Gemini returned an empty response.")

    try:
        return _parse_json_response(text)
    except json.JSONDecodeError as exc:
        raise GeminiFallbackError(f"Gemini response was not valid JSON: {exc}") from exc


def gemini_to_standard(gemini_result: dict, austria_only: bool = True) -> dict[str, dict]:
    """Map a Gemini Vision response into the script's standard coord shape.

    Returns a dict with optional ``lat`` / ``lon`` keys, each holding the
    same fields ``enrich()`` produces in ``extract_gps_paddle_v2``.
    Coords outside the Austria bbox are dropped when ``austria_only``.
    """
    out: dict[str, dict] = {}
    for axis in ("lat", "lon"):
        coord = gemini_result.get(axis)
        if not isinstance(coord, dict):
            continue
        decimal = coord.get("decimal")
        if not isinstance(decimal, (int, float)):
            continue
        decimal = float(decimal)

        if austria_only:
            lo, hi = AUSTRIA_LAT if axis == "lat" else AUSTRIA_LON
            if not (lo <= decimal <= hi):
                continue

        conf_label = str(coord.get("confidence") or "medium").lower()
        ocr_conf = CONFIDENCE_MAP.get(conf_label, 0.5)
        flag = "HIGH" if ocr_conf >= FLAG_THRESHOLD else "LOW"
        flag_reason = (
            "gemini_vision_confidence_high"
            if flag == "HIGH"
            else f"gemini_vision_confidence_{conf_label}"
        )

        out[axis] = {
            "decimal": round(decimal, 10),
            "dms": _decimal_to_dms(decimal, axis),
            "raw_ocr": str(coord.get("raw") or ""),
            "format": "gemini_vision",
            "ocr_confidence": round(ocr_conf, 4),
            "flag": flag,
            "flag_reason": flag_reason,
            "source_band": "gemini_vision_fallback",
        }
    return out


def run_gemini_fallback(image_path: Path) -> tuple[dict[str, dict], dict[str, Any]]:
    """High-level helper for ``extract_gps_paddle_v2``.

    Returns ``(standard, raw)`` where ``standard`` is the pipeline-shape
    dict ready to merge into ``gps[...]``, and ``raw`` is the original
    Gemini JSON payload for debugging.
    """
    raw = call_gemini_vision(image_path)
    standard = gemini_to_standard(raw)
    return standard, raw

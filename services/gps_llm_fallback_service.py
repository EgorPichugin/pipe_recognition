from __future__ import annotations

from base64 import b64encode
from io import BytesIO
import json
import logging
import os

from PIL import Image

from services.gps_extractor import GpsExtractionResult
from services.gps_parser import AUSTRIA_LAT, AUSTRIA_LON


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

DEFAULT_OPENAI_MODEL = "gpt-4.1-mini"
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"

LLM_PROMPT = (
    "Read the visible GPS coordinate watermark in this image. "
    "Return only JSON with keys: latitude, longitude, confidence_level. "
    "confidence_level must be GPS_HIGH if both coordinates are clearly "
    "readable, otherwise GPS_LOW. Use decimal degrees. If coordinates are "
    "not readable, return {\"latitude\": null, \"longitude\": null, "
    "\"confidence_level\": \"NO_GPS\"}. Do not guess."
)


def get_image_mime_type(image_bytes: bytes) -> str:
    try:
        with Image.open(BytesIO(image_bytes)) as image:
            image_format = (image.format or "").lower()
    except Exception:
        return "image/jpeg"

    if image_format == "png":
        return "image/png"
    if image_format == "webp":
        return "image/webp"
    return "image/jpeg"


def is_valid_austria_location(latitude: float, longitude: float) -> bool:
    return (
        AUSTRIA_LAT[0] <= latitude <= AUSTRIA_LAT[1]
        and AUSTRIA_LON[0] <= longitude <= AUSTRIA_LON[1]
    )


def parse_llm_response(text: str) -> GpsExtractionResult | None:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None
        try:
            payload = json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return None

    latitude = payload.get("latitude")
    longitude = payload.get("longitude")
    if not isinstance(latitude, (int, float)) or not isinstance(longitude, (int, float)):
        return None

    latitude = float(latitude)
    longitude = float(longitude)
    if not is_valid_austria_location(latitude, longitude):
        logger.warning(
            "LLM GPS fallback returned coordinates outside Austria: lat=%s lon=%s",
            latitude,
            longitude,
        )
        return None

    confidence_level = str(payload.get("confidence_level") or "GPS_LOW")
    if confidence_level not in {"GPS_HIGH", "GPS_LOW"}:
        confidence_level = "GPS_LOW"

    return GpsExtractionResult(
        latitude=latitude,
        longitude=longitude,
        confidence_level=confidence_level,
    )


def _call_openai(image_bytes: bytes) -> str | None:
    try:
        from openai import OpenAI
    except ImportError:
        logger.warning("Skipping OpenAI LLM fallback: openai package not installed.")
        return None

    image_base64 = b64encode(image_bytes).decode("utf-8")
    mime_type = get_image_mime_type(image_bytes)
    model = os.getenv("OPENAI_GPS_MODEL", DEFAULT_OPENAI_MODEL)
    client = OpenAI()

    response = client.responses.create(
        model=model,
        input=[
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": LLM_PROMPT},
                    {
                        "type": "input_image",
                        "image_url": f"data:{mime_type};base64,{image_base64}",
                        "detail": "high",
                    },
                ],
            }
        ],
    )
    return response.output_text


def _call_gemini(image_bytes: bytes) -> str | None:
    try:
        import google.generativeai as genai
    except ImportError:
        logger.warning("Skipping Gemini LLM fallback: google-generativeai not installed.")
        return None

    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
    model_name = os.getenv("GEMINI_MODEL", DEFAULT_GEMINI_MODEL)
    mime_type = get_image_mime_type(image_bytes)
    model = genai.GenerativeModel(model_name)

    response = model.generate_content(
        [
            LLM_PROMPT,
            {"mime_type": mime_type, "data": image_bytes},
        ],
        generation_config={"response_mime_type": "application/json"},
    )
    return response.text


def extract_gps_with_llm(image_bytes: bytes) -> GpsExtractionResult | None:
    if os.getenv("OPENAI_API_KEY"):
        provider = "openai"
        raw_text = _call_openai(image_bytes)
    elif os.getenv("GEMINI_API_KEY"):
        provider = "gemini"
        raw_text = _call_gemini(image_bytes)
    else:
        logger.warning("Skipping LLM GPS fallback: no OPENAI_API_KEY or GEMINI_API_KEY set.")
        return None

    if raw_text is None:
        return None

    result = parse_llm_response(raw_text)
    if result is None:
        logger.warning(
            "LLM GPS fallback (%s) returned no usable coordinates. raw=%r",
            provider,
            raw_text[:300] if raw_text else raw_text,
        )
    else:
        logger.info(
            "LLM GPS fallback (%s) found coordinates: lat=%s lon=%s confidence=%s",
            provider,
            result.latitude,
            result.longitude,
            result.confidence_level,
        )
    return result

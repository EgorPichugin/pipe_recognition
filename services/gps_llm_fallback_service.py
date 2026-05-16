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

DEFAULT_MODEL = "gpt-4.1-mini"


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


def extract_gps_with_openai_vision(image_bytes: bytes) -> GpsExtractionResult | None:
    if not os.getenv("OPENAI_API_KEY"):
        logger.warning("Skipping LLM GPS fallback because OPENAI_API_KEY is not set.")
        return None

    try:
        from openai import OpenAI
    except ImportError:
        logger.warning("Skipping LLM GPS fallback because openai is not installed.")
        return None

    image_base64 = b64encode(image_bytes).decode("utf-8")
    mime_type = get_image_mime_type(image_bytes)
    model = os.getenv("OPENAI_GPS_MODEL", DEFAULT_MODEL)
    client = OpenAI()

    response = client.responses.create(
        model=model,
        input=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": (
                            "Read the visible GPS coordinate watermark in this image. "
                            "Return only JSON with keys: latitude, longitude, "
                            "confidence_level. confidence_level must be GPS_HIGH if "
                            "both coordinates are clearly readable, otherwise GPS_LOW. "
                            "Use decimal degrees. If coordinates are not readable, "
                            "return {\"latitude\": null, \"longitude\": null, "
                            "\"confidence_level\": \"NO_GPS\"}. Do not guess."
                        ),
                    },
                    {
                        "type": "input_image",
                        "image_url": f"data:{mime_type};base64,{image_base64}",
                        "detail": "high",
                    },
                ],
            }
        ],
    )

    result = parse_llm_response(response.output_text)
    if result is None:
        logger.warning("LLM GPS fallback did not return usable coordinates.")
    else:
        logger.info(
            "LLM GPS fallback found coordinates: lat=%s lon=%s confidence=%s",
            result.latitude,
            result.longitude,
            result.confidence_level,
        )
    return result

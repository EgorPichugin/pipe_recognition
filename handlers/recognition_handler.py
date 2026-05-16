from base64 import b64decode
from binascii import Error as Base64Error

from fastapi import HTTPException

from models.requests import RecognitionRequest
from models.responses import RecognitionResponse
from services.image_hash_service import create_image_hashvalue
from services.recognition_service import (
    get_recognition_by_image_hashvalue,
    get_recognition_by_image_name,
    save_recognition_result,
)
from services.yolo_service import run_yolo_recognition


def decode_image(image: str) -> bytes:
    if "," in image and image.strip().lower().startswith("data:"):
        image = image.split(",", 1)[1]

    try:
        return b64decode(image, validate=True)
    except (Base64Error, ValueError):
        raise HTTPException(status_code=400, detail="image must be valid base64")


def handle_recognition(request: RecognitionRequest) -> RecognitionResponse:
    image_bytes = decode_image(request.image)
    return handle_recognition_bytes(
        id=request.id,
        image_name=request.image_name,
        image_bytes=image_bytes,
    )


def handle_recognition_bytes(
    id: int,
    image_name: str,
    image_bytes: bytes,
) -> RecognitionResponse:
    existing_result = get_recognition_by_image_name(image_name)
    if existing_result is not None:
        return existing_result

    if not image_bytes:
        raise HTTPException(status_code=400, detail="image cannot be empty")

    image_hashvalue = create_image_hashvalue(image_bytes)
    existing_result = get_recognition_by_image_hashvalue(image_hashvalue)
    if existing_result is not None:
        return existing_result

    category, latitude, longitude, confidence = run_yolo_recognition(
        image_bytes,
        image_name,
    )

    result = RecognitionResponse(
        id=id,
        image_name=image_name,
        category=category,
        latitude=latitude,
        longitude=longitude,
        confidence=confidence,
        status="created",
    )
    save_recognition_result(image_name, image_hashvalue, result)

    return result

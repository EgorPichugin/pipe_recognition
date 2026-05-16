from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from io import BytesIO
import logging
from pathlib import Path
import time
from typing import Any

import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

_ocr_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="ocr")

from services.gps_parser import (
    StrictDmsError,
    crop_bands,
    parse_coordinates,
    validate_austria,
)


OCR_CONFIDENCE_THRESHOLD = 0.90


@dataclass(frozen=True)
class GpsExtractionResult:
    latitude: float
    longitude: float
    confidence_level: str
    latitude_ocr_confidence: float | None = None
    longitude_ocr_confidence: float | None = None


_ocr = None


def get_ocr():
    global _ocr
    if _ocr is None:
        try:
            from paddleocr import PaddleOCR
        except ImportError as exc:
            raise RuntimeError(
                "paddleocr is not installed. Run: pip install paddlepaddle paddleocr"
            ) from exc

        mobile_models = {
            "text_detection_model_name": "PP-OCRv5_mobile_det",
            "text_recognition_model_name": "latin_PP-OCRv5_mobile_rec",
        }
        for kwargs in (
            {**mobile_models, "lang": "german", "use_textline_orientation": True},
            {**mobile_models, "lang": "german"},
            {"lang": "german"},
        ):
            try:
                _ocr = PaddleOCR(**kwargs)
                break
            except (TypeError, ValueError):
                continue
        if _ocr is None:
            _ocr = PaddleOCR(lang="german")

    return _ocr


def run_ocr(ocr, image: Image.Image) -> list[tuple[str, float]]:
    arr = np.array(image.convert("RGB"))
    detections: list[tuple[str, float]] = []

    if hasattr(ocr, "predict"):
        predictions = ocr.predict(arr)
        for prediction in predictions:
            if isinstance(prediction, dict):
                texts = prediction.get("rec_texts", []) or prediction.get("rec_text", [])
                scores = prediction.get("rec_scores", []) or prediction.get("rec_score", [])
                for text, score in zip(texts, scores):
                    detections.append((str(text), float(score)))
            else:
                for line in prediction:
                    if line:
                        _bbox, (text, score) = line[0], line[1]
                        detections.append((str(text), float(score)))
        return detections

    predictions = ocr.ocr(arr)
    if predictions and predictions[0]:
        for line in predictions[0]:
            if line:
                _bbox, (text, score) = line
                detections.append((str(text), float(score)))

    return detections


def find_best_coordinates(
    detections: list[tuple[str, float]],
) -> tuple[dict[str, Any] | None, dict[str, Any] | None, float | None, float | None]:
    best_lat = None
    best_lon = None
    best_lat_confidence: float | None = None
    best_lon_confidence: float | None = None

    def consider(text: str, confidence: float) -> None:
        nonlocal best_lat, best_lon, best_lat_confidence, best_lon_confidence
        try:
            parsed = parse_coordinates(text)
        except StrictDmsError:
            return

        valid = validate_austria(parsed)
        if "lat" in valid and (
            best_lat_confidence is None or confidence > best_lat_confidence
        ):
            best_lat = valid["lat"]
            best_lat_confidence = confidence
        if "lon" in valid and (
            best_lon_confidence is None or confidence > best_lon_confidence
        ):
            best_lon = valid["lon"]
            best_lon_confidence = confidence

    for text, confidence in detections:
        consider(text, confidence)

    joined_text = " ".join(text for text, _ in detections)
    if joined_text:
        joined_confidence = min((confidence for _, confidence in detections), default=0.0)
        consider(joined_text, joined_confidence)

    return best_lat, best_lon, best_lat_confidence, best_lon_confidence


def confidence_level(
    latitude: dict[str, Any] | None,
    longitude: dict[str, Any] | None,
    latitude_confidence: float | None,
    longitude_confidence: float | None,
) -> str:
    if latitude is None and longitude is None:
        return "NO_GPS"
    if latitude is None or longitude is None:
        return "GPS_LOW"
    if (
        latitude_confidence is not None
        and longitude_confidence is not None
        and latitude_confidence >= OCR_CONFIDENCE_THRESHOLD
        and longitude_confidence >= OCR_CONFIDENCE_THRESHOLD
    ):
        return "GPS_HIGH"
    return "GPS_LOW"


def _run_ocr_timed(ocr, band: Image.Image) -> tuple[list[tuple[str, float]], float]:
    t0 = time.perf_counter()
    detections = run_ocr(ocr, band)
    return detections, time.perf_counter() - t0


def extract_gps_from_image(image: Image.Image) -> GpsExtractionResult:
    t0 = time.perf_counter()
    ocr = get_ocr()
    t_init = time.perf_counter() - t0
    all_detections: list[tuple[str, float]] = []

    bands = crop_bands(image.convert("RGB"))
    band_times: dict[str, float] = {}

    t_par = time.perf_counter()
    futures = {
        name: _ocr_executor.submit(_run_ocr_timed, ocr, band)
        for name, band in bands.items()
    }
    for name, future in futures.items():
        detections, duration = future.result()
        band_times[name] = duration
        all_detections.extend(detections)
    t_par_total = time.perf_counter() - t_par

    t_full = 0.0
    if not all_detections:
        t_f = time.perf_counter()
        all_detections.extend(run_ocr(ocr, image))
        t_full = time.perf_counter() - t_f

    logger.info(
        "TIMING ocr_breakdown init=%.3fs top=%.3fs bottom=%.3fs parallel_wall=%.3fs full=%.3fs detections=%d image_size=%sx%s",
        t_init,
        band_times.get("top_band", 0.0),
        band_times.get("bottom_band", 0.0),
        t_par_total,
        t_full,
        len(all_detections),
        image.size[0],
        image.size[1],
    )

    latitude, longitude, latitude_confidence, longitude_confidence = find_best_coordinates(
        all_detections
    )

    return GpsExtractionResult(
        latitude=latitude["value"] if latitude else 0.0,
        longitude=longitude["value"] if longitude else 0.0,
        confidence_level=confidence_level(
            latitude,
            longitude,
            latitude_confidence,
            longitude_confidence,
        ),
        latitude_ocr_confidence=latitude_confidence,
        longitude_ocr_confidence=longitude_confidence,
    )


def extract_gps_from_path(image_path: str | Path) -> GpsExtractionResult:
    with Image.open(image_path) as image:
        return extract_gps_from_image(image)


def extract_gps_from_bytes(image_bytes: bytes) -> GpsExtractionResult:
    with Image.open(BytesIO(image_bytes)) as image:
        return extract_gps_from_image(image)

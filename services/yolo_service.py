from io import BytesIO
import logging
import os
from pathlib import Path
import re

from fastapi import HTTPException
from PIL import Image


MODEL_PATH = Path("yolo_models") / "best.pt"
OBJECTS_DETECTED_PATH = Path("objects_detected")
YOLO_CONFIG_PATH = Path(".ultralytics")
COMBINED_DUCT_WIRE_CLASSES = {"duct", "wire"}
CATEGORY_CLASSES = {"tape", *COMBINED_DUCT_WIRE_CLASSES}
TARGET_CLASSES = {"address", *CATEGORY_CLASSES}
_model = None
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def get_model():
    global _model
    if _model is None:
        YOLO_CONFIG_PATH.mkdir(exist_ok=True)
        os.environ.setdefault("YOLO_CONFIG_DIR", str(YOLO_CONFIG_PATH.resolve()))

        try:
            from ultralytics import YOLO
        except ImportError:
            raise HTTPException(
                status_code=500,
                detail="ultralytics is not installed. Run: pip install ultralytics",
            )

        if not MODEL_PATH.exists():
            raise HTTPException(status_code=500, detail=f"YOLO model not found: {MODEL_PATH}")

        _model = YOLO(MODEL_PATH)

    return _model


def assign_category(detected_classes: set[str]) -> int:
    has_tape = "tape" in detected_classes
    has_duct_or_wire = "duct_or_wire" in detected_classes

    if not has_tape and not has_duct_or_wire:
        return 4
    if not has_tape and has_duct_or_wire:
        return 2
    if has_tape and not has_duct_or_wire:
        return 3
    if has_tape and has_duct_or_wire:
        return 1

    return 4


def safe_output_path(image_name: str) -> Path:
    OBJECTS_DETECTED_PATH.mkdir(exist_ok=True)
    source_path = Path(image_name)
    stem = re.sub(r"[^A-Za-z0-9_.-]", "_", source_path.stem).strip("._")
    if not stem:
        stem = "processed_image"

    return OBJECTS_DETECTED_PATH / f"{stem}_detected.jpg"


def save_processed_image(result, image_name: str) -> None:
    plotted_image = result.plot()
    rgb_image = plotted_image[..., ::-1]
    Image.fromarray(rgb_image).save(safe_output_path(image_name), format="JPEG")


def log_class_scores(image_name: str, class_confidences: dict[str, float]) -> None:
    scores = {
        class_name: class_confidences.get(class_name, 0.0)
        for class_name in sorted(TARGET_CLASSES)
    }
    logger.info(
        "YOLO max scores for %s: address=%.4f duct=%.4f tape=%.4f wire=%.4f",
        image_name,
        scores["address"],
        scores["duct"],
        scores["tape"],
        scores["wire"],
    )


def get_category_signals(class_confidences: dict[str, float]) -> dict[str, float]:
    duct_or_wire_confidence = max(
        class_confidences.get("duct", 0.0),
        class_confidences.get("wire", 0.0),
    )
    signals = {}

    if class_confidences.get("tape", 0.0) > 0.0:
        signals["tape"] = class_confidences["tape"]
    if duct_or_wire_confidence > 0.0:
        signals["duct_or_wire"] = duct_or_wire_confidence

    return signals


def run_yolo_recognition(
    image_bytes: bytes,
    image_name: str,
) -> tuple[int, float, float, float]:
    try:
        image = Image.open(BytesIO(image_bytes)).convert("RGB")
    except Exception:
        raise HTTPException(status_code=400, detail="image must be a valid image file")

    model = get_model()
    results = model.predict(image, verbose=False)
    if not results:
        return 4, 0.0, 0.0, 0.0

    result = results[0]
    save_processed_image(result, image_name)
    names = result.names
    class_confidences: dict[str, float] = {}

    if result.boxes is not None:
        for box in result.boxes:
            class_id = int(box.cls.item())
            class_name = str(names[class_id]).lower()
            confidence = float(box.conf.item())

            if class_name in TARGET_CLASSES:
                class_confidences[class_name] = max(
                    confidence,
                    class_confidences.get(class_name, 0.0),
                )

    log_class_scores(image_name, class_confidences)
    category_signals = get_category_signals(class_confidences)
    category = assign_category(set(category_signals))
    confidence_scores = list(category_signals.values())
    confidence = min(confidence_scores) if confidence_scores else 0.0
    return category, 0.0, 0.0, confidence

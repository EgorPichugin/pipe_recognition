import os
from pathlib import Path

from dotenv import load_dotenv


DUMMY_JSON_RESPONSE = {
    "report_date": "2026-05-09",
    "summary": "Several wall cracks and installation defects were detected.",
    "issues": [
        "Crack near window frame",
        "Missing sealant around door",
        "Uneven wall finish",
    ],
}

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(_PROJECT_ROOT / ".env")

IMAGE_PATH = "src/docs/images/sample_wall_image.jpg"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_REPORT_MODEL = "gpt-5.5"

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

PHOTOS_DATA_PATH = _PROJECT_ROOT / "src" / "docs" / "data" / "sample_photos.json"
PHOTOS_IMAGE_DIR = _PROJECT_ROOT / "src" / "docs" / "images" / "photos"

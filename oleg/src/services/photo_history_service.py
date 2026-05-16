import csv
import io
import json
from pathlib import Path
from typing import Iterable

from src.core.config import PHOTOS_DATA_PATH
from src.models.photos import PhotoRecord


class PhotoHistoryService:
    def __init__(self, data_path: Path = PHOTOS_DATA_PATH) -> None:
        self._data_path = data_path
        self._photos: list[PhotoRecord] = self._load()

    def _load(self) -> list[PhotoRecord]:
        if not self._data_path.exists():
            return []
        raw = json.loads(self._data_path.read_text(encoding="utf-8"))
        return [PhotoRecord.model_validate(item) for item in raw]

    def list_photos(self) -> list[PhotoRecord]:
        return list(self._photos)

    def replace(self, photos: Iterable[PhotoRecord]) -> list[PhotoRecord]:
        self._photos = list(photos)
        return self.list_photos()

    def export_csv(self) -> str:
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(["id", "latitude", "longitude", "image_name", "category", "status"])
        for photo in self._photos:
            writer.writerow(
                [
                    photo.id,
                    photo.latitude,
                    photo.longitude,
                    photo.image_name,
                    photo.category,
                    photo.status,
                ]
            )
        return buffer.getvalue()


photo_history_service = PhotoHistoryService()

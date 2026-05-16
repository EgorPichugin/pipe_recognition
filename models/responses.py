from typing import Literal

from pydantic import BaseModel


class RecognitionResponse(BaseModel):
    id: int
    image_name: str
    category: int
    latitude: float
    longitude: float
    confidence: float
    status: Literal["created", "duplicate_name", "duplicate_image"]

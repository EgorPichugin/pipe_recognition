from pydantic import BaseModel, Field


class RecognitionRequest(BaseModel):
    id: int
    image_name: str
    image: str = Field(
        ...,
        description="Base64 encoded image data. A data URL prefix is also accepted.",
    )

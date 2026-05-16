from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI, File, Form, UploadFile

from database import init_db
from handlers.recognition_handler import handle_recognition, handle_recognition_bytes
from models.requests import RecognitionRequest
from models.responses import RecognitionResponse


logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s:     %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Pipe Recognition API", lifespan=lifespan)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/recognize", response_model=RecognitionResponse)
def recognize_pipe(request: RecognitionRequest) -> RecognitionResponse:
    return handle_recognition(request)


@app.post("/recognize/upload", response_model=RecognitionResponse)
async def recognize_pipe_upload(
    id: int = Form(...),
    image: UploadFile = File(...),
) -> RecognitionResponse:
    image_bytes = await image.read()
    image_name = image.filename or "uploaded_image"
    return handle_recognition_bytes(
        id=id,
        image_name=image_name,
        image_bytes=image_bytes,
    )

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)

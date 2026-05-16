from contextlib import asynccontextmanager
import logging

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse


load_dotenv()

from database import init_db
from handlers.recognition_handler import handle_recognition, handle_recognition_bytes
from models.requests import RecognitionRequest
from models.responses import RecognitionResponse
from services.map_service import build_map
from services.recognition_service import get_all_recognitions


logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s:     %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Pipe Recognition API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
    image_name = image.filename or f"uploaded_image_{id}"
    return handle_recognition_bytes(
        id=id,
        image_name=image_name,
        image_bytes=image_bytes,
    )

@app.get("/map", response_class=HTMLResponse)
def get_map() -> HTMLResponse:
    rows = get_all_recognitions()
    if not rows:
        return HTMLResponse("<h3 style='font-family:sans-serif;padding:1rem'>No recognitions yet.</h3>")
    try:
        html = build_map([r.model_dump() for r in rows])
    except ValueError:
        return HTMLResponse("<h3 style='font-family:sans-serif;padding:1rem'>No valid GPS points yet.</h3>")
    return HTMLResponse(html)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)

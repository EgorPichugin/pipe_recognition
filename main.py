from contextlib import asynccontextmanager
import logging

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware


load_dotenv()

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


@app.post("/recognize/upload/batch", response_model=list[RecognitionResponse])
async def recognize_pipe_upload_batch(
    ids: list[int] = Form(...),
    images: list[UploadFile] = File(...),
) -> list[RecognitionResponse]:
    if not images:
        raise HTTPException(status_code=400, detail="images cannot be empty")

    if len(ids) != len(images):
        raise HTTPException(
            status_code=400,
            detail="ids and images must contain the same number of items",
        )
    print(len(ids), len(images))
    results: list[RecognitionResponse] = []
    for index, (id, image) in enumerate(zip(ids, images), start=1):
        image_bytes = await image.read()
        image_name = image.filename or f"uploaded_image_{id}_{index}"
        results.append(
            handle_recognition_bytes(
                id=id,
                image_name=image_name,
                image_bytes=image_bytes,
            )
        )

    return results


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)

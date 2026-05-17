# Pipe Recognition

Detect what's visible in a buried-pipe inspection photo and put it on a map.

Given a single photo from a construction site, the service identifies which
protective elements are present (warning tape, ducts, wires), reads the
GPS watermark stamped onto the image by the surveyor's camera app, and
returns a structured record. All records are aggregated into an
interactive Leaflet map.

Companion frontend (Nuxt 4):
[EgorPichugin/pipe-recognition-client](https://github.com/EgorPichugin/pipe-recognition-client) — deployed at
[pipe-recognition-client.vercel.app](https://pipe-recognition-client.vercel.app/architecture).

---

## What it does

The pipeline takes one image and runs it through five stages:

1. **Dedup** — a perceptual hash is computed; if the same image (by name or
   hash) was processed before, the cached record is returned and the rest
   of the pipeline is skipped.
2. **YOLO detection** — a custom Ultralytics model
   (`yolo_models/best.pt`) classifies four object types: `address`,
   `tape`, `duct`, `wire`. The combination of detected classes determines
   the **category** (1–4) reported back.
3. **GPS extraction** — the top and bottom 40% bands of the image are
   passed through PaddleOCR (PP-OCRv5 mobile, German latin) in parallel,
   then a chain of regexes
   ([`services/gps_parser.py`](services/gps_parser.py)) tries to parse
   DMS or decimal coordinates from the OCR output. Results are validated
   against the Austria bounding box.
4. **LLM fallback** — if OCR fails or the parsed coordinates are flagged
   `NO_GPS`, the image is sent to a vision LLM (OpenAI GPT-4.1 mini if
   `OPENAI_API_KEY` is set, otherwise Gemini 2.5 Flash if
   `GEMINI_API_KEY` is set). The model returns JSON with
   latitude/longitude or `null`s.
5. **Report assembly** — the per-image result (category, coordinates,
   confidence) is persisted to SQLite for dedup and aggregation. The
   `/map` endpoint then assembles all stored results into a single
   structured report: an interactive Folium/Leaflet map where every
   processed photo appears as a colour-coded marker (category → colour)
   with a tooltip showing image name and confidence. The frontend
   embeds this map and shows a per-photo report card next to it, so the
   findings are review-ready for export or follow-up decisions.

### Category meaning (YOLO output)

| Category | Tape detected | Duct/wire detected | Meaning |
|----------|---------------|--------------------|---------|
| 1 | yes | yes | Best: warning tape **and** conduit visible |
| 2 | no | yes | Conduit only |
| 3 | yes | no | Tape only |
| 4 | no | no | Neither found |

Category drives marker colour on the map (green / orange / red / gray).

---

## API

Base URL during local dev: `http://localhost:8000`. Swagger UI at
`http://localhost:8000/docs`.

### `GET /health`

Liveness probe. Returns `{"status": "ok"}`.

### `POST /recognize`

Single-image recognition via JSON.

Request body ([`models/requests.py`](models/requests.py)):

```json
{
  "id": 1,
  "image_name": "site42.jpg",
  "image": "<base64 string, with or without `data:image/...;base64,` prefix>"
}
```

Response ([`models/responses.py`](models/responses.py)):

```json
{
  "id": 1,
  "image_name": "site42.jpg",
  "category": 2,
  "latitude": 46.563637,
  "longitude": 14.291149,
  "confidence": 0.96,
  "status": "created"
}
```

`status` is `created` for a fresh result, or `duplicate_name` /
`duplicate_image` when a cached record is returned.

### `POST /recognize/upload`

Same recognition flow but accepts `multipart/form-data` with fields
`id` (int) and `image` (file).

### `POST /recognize/upload/batch`

Multipart endpoint that accepts repeated `ids` and `images` fields
(same count required) and returns a list of `RecognitionResponse`
records in input order.

### `GET /map`

Returns a self-contained HTML document with a Leaflet map of every
record currently in the database. Markers are coloured by category and
hovering shows `image_name — confidence: NN.NN%`. When no records exist
yet (or all of them are outside the Austria bbox), a small placeholder
HTML is returned instead.

The frontend embeds this directly via an `<iframe>` and reloads it
after every successful recognition.

---

## Quick start

### Prerequisites

- **Python 3.13 (maximum).** PaddleOCR / `paddlepaddle` do not yet
  ship wheels for Python 3.14+, so the OCR stage will fail to install
  on newer interpreters. 3.11–3.13 are known to work; the repo was
  developed against 3.13. If you have a newer Python as default,
  create the venv explicitly: `python3.13 -m venv .venv`.
- The YOLO weights at [`yolo_models/best.pt`](yolo_models/best.pt) — committed in the repo

### Install

```bash
git clone git@github.com:EgorPichugin/pipe_recognition.git
cd pipe_recognition

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

On first run, PaddleOCR will download its detection/recognition models
(~80 MB total) into `~/.paddlex/official_models/`. Subsequent runs reuse
the cache.

### Configure

Create a `.env` in the project root:

```bash
# Pick one of the two for the LLM fallback. If neither is set, the
# fallback is skipped silently and photos without a readable watermark
# produce (0, 0) coordinates.
OPENAI_API_KEY=""
GEMINI_API_KEY=""

# Optional overrides:
OPENAI_GPS_MODEL=gpt-4.1-mini
GEMINI_MODEL=gemini-2.5-flash
```

The LLM fallback prefers OpenAI when both keys are present.

### Run

```bash
python main.py
```

Server listens on `0.0.0.0:8000`. CORS is open for `localhost:3000` so
the Nuxt frontend works out of the box.

### Smoke test

```bash
curl -X POST http://localhost:8000/recognize/upload \
  -F "id=1" \
  -F "image=@/path/to/photo.jpg"

# View the aggregate map in a browser:
open http://localhost:8000/map
```

---

## Project layout

```
.
├── main.py                       FastAPI app + route definitions
├── database.py                   SQLite schema + init
├── handlers/
│   └── recognition_handler.py    Orchestrates dedup → YOLO → OCR → LLM
├── services/
│   ├── yolo_service.py           Ultralytics YOLO inference
│   ├── gps_extractor.py          PaddleOCR pipeline (parallel band OCR)
│   ├── gps_parser.py             DMS / decimal regex parsing, Austria bbox
│   ├── gps_llm_fallback_service.py   OpenAI / Gemini vision fallback
│   ├── map_service.py            Folium map rendering
│   ├── recognition_service.py    SQLite read/write
│   └── image_hash_service.py     Perceptual hash for dedup
├── models/
│   ├── requests.py               Pydantic request schemas
│   └── responses.py              Pydantic response schemas
├── yolo_models/best.pt           Trained YOLO weights
└── requirements.txt
```

Build artefacts (not committed):
- `pipe_recognition.db` — SQLite DB
- `objects_detected/` — YOLO annotated previews, one per request
- `.ultralytics/` — Ultralytics runtime config

---

## Key metrics

| Metric | Value | Notes |
|---|---|---|
| **Accuracy above threshold** | **100%** | 0 errors at YOLO confidence ≥ 90% |
| **Per-photo inference** | **~10 s** | Single-frame end-to-end on the local CV pipeline |
| **Cost per 1 000 photos (our stack)** | **€0** | Self-hosted YOLO + PaddleOCR — no per-call API fees |
| **Cost per 1 000 photos (cloud vision API)** | **€15+** | Same volume routed through a cloud vision LLM |

The recognition pipeline emits structured `TIMING ...` log lines for
every request to make these numbers reproducible:

```
TIMING yolo=0.821s name=...
TIMING ocr_breakdown init=0.000s top=2.609s bottom=1.548s bands_total=4.157s full=0.000s detections=8 image_size=1536x2048
TIMING ocr=4.183s result=GPS_HIGH name=...
TIMING llm_fallback=0.000s name=...
```

OCR dominates the cost. An earlier experiment ran the top and bottom
bands through PaddleOCR in parallel via a `ThreadPoolExecutor`, but the
underlying engine is already CPU-bound through OpenMP, so two workers
ended up contending for the same cores with little net speedup —
sequential execution is the current default. Roadmap for further wins:
down-scaling oversized inputs before OCR, running YOLO concurrently
with OCR, capping `OMP_NUM_THREADS` so band-level parallelism can pay
off, and warming both models in the FastAPI `lifespan`.

---

## Known limitations

- **Austria bbox is hard-coded**
  ([`services/gps_parser.py:30-31`](services/gps_parser.py#L30-L31)).
  Coordinates outside `(46.0…49.5, 9.0…17.5)` are dropped, including by
  the LLM fallback. Adjust the constants to extend support.
- **WhatsApp re-compresses photos.** The GPS watermark survives in many
  cases but not all. When OCR fails *and* the LLM also returns null
  coordinates, the record is still saved with `latitude=0, longitude=0`;
  the map filters those out automatically.
- **`google-generativeai` is deprecated.** It still works but emits a
  `FutureWarning`. Migration target is `google-genai`.

---

## Tech stack

- [FastAPI](https://fastapi.tiangolo.com/) + Uvicorn
- [Ultralytics YOLO](https://docs.ultralytics.com/) (custom-trained weights)
- [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR) PP-OCRv5 mobile
- [Folium](https://python-visualization.github.io/folium/) for map rendering
- [OpenAI](https://platform.openai.com/) / [Gemini](https://ai.google.dev/) vision APIs (fallback)
- SQLite for caching recognition results

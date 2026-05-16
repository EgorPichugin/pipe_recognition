# Inspection AI — архитектура проекта

Хакатон Vienna. Пайплайн: пользователь загружает фото объекта (со штампом гео-водяного знака от GPS Map Camera), система прогоняет их через OCR + детектор объектов и собирает инспекционный отчёт.

## Пайплайн (8 шагов)

| # | Шаг | Где живёт | Статус |
|---|-----|-----------|--------|
| 1 | **Инпут**: одно фото или батч от пользователя | `frontend/components/InputSection.vue` → `POST /report/preview` | частично — UI принимает одну картинку, батч и приём сырых файлов на бэкенде ещё не разведены |
| 2 | **Имя + хэш**: дедуп, проверка расширения, sha256 | — | НЕТ |
| 3 | **OCR** для гео-водяного знака | `scripts/extract_gps_paddle_v2.py` (использует парсинг из `extract_gps.py`, Gemini-fallback в `gemini_gps_fallback.py`) | ЕСТЬ, но как standalone CLI — не подключено к FastAPI |
| 4 | **YOLO** + категоризация объектов на фото | — | НЕТ |
| 5 | **Нанесение гео-меток на карту** | `scripts/summarize_gps.py` собирает CSV/MD сводку; рендера карты нет | частично — есть агрегация, нет визуализации |
| 6 | **Генерация репорта** (DOCX) | `src/services/report_service.py` + `src/models/report.py` | ЕСТЬ на дамми-данных; реальный пайплайн не питает его |
| 7 | **Оценка репорта** / QA на ошибки | — (есть `report_edit_planner.py`, но это другое — он применяет правки от юзера через OpenAI) | НЕТ |
| 8 | **Вывод юзеру** | `frontend/components/OutputSection.vue` ← `GET /report/schema` + `GET /report/preview` (DOCX) | ЕСТЬ |

## Структура репозитория

```
repo/
├─ frontend/                          # Nuxt 3 + Vue 3 + Tailwind, dev на :3000, проксит /report/* → :8000
│  ├─ pages/index.vue                 # композит лендинга
│  ├─ components/
│  │  ├─ SiteNav.vue HeroSection.vue
│  │  ├─ ArchitectureSection.vue      # уже рисует диаграмму пайплайна
│  │  ├─ InputSection.vue             # загрузка фото + requirements → POST /report/preview
│  │  ├─ OutputSection.vue            # рендер схемы + кнопка скачать DOCX + reset
│  │  ├─ MetricsSection.vue SiteFooter.vue
│  │  └─ Arrow*.vue                   # SVG-коннекторы
│  ├─ composables/useReportApi.ts     # типизированные fetch-обёртки + тип ReportSchema
│  └─ nuxt.config.ts                  # devProxy на FastAPI
│
├─ src/                               # FastAPI backend, uvicorn :8000
│  ├─ main.py                         # точка входа
│  ├─ core/
│  │  ├─ app.py                       # create_app, include_router
│  │  └─ config.py                    # _PROJECT_ROOT, IMAGE_PATH
│  ├─ routers/
│  │  └─ report_router.py             # GET/POST /report/preview, GET /report/schema, POST /report/reset
│  ├─ services/
│  │  ├─ report_service.py            # in-memory отчёт, DOCX-рендер через python-docx, патчи
│  │  └─ report_edit_planner.py       # OpenAI-планировщик правок (intent + ReportPatch)
│  ├─ models/
│  │  └─ report.py                    # Pydantic: ReportSchema, ReportPatch, ReportEditPlan, build_dummy_report()
│  └─ docs/images/sample_wall_image.jpg
│
├─ scripts/                           # офлайновые CLI-инструменты (не подключены к API)
│  ├─ extract_gps.py                  # ядро: парсинг DMS/decimal, валидация Австрии
│  ├─ extract_gps_paddle.py           # PaddleOCR вариант (легаси)
│  ├─ extract_gps_paddle_v2.py        # актуальный: PaddleOCR mobile + 3-флаг confidence + --input-json
│  ├─ gemini_gps_fallback.py          # LLM-fallback на GPS_LOW / NO_GPS (Google Gemini Vision)
│  └─ summarize_gps.py                # сводка JSON → CSV + MD
│
├─ out/                               # выхлоп скриптов (не коммитим в прод)
│  ├─ ocr/ gps/ gps_apple/ gps_paddle/ gps_paddle_mobile/
│  └─ ...
│
├─ requirements.txt                   # fastapi, uvicorn, docxtpl, python-docx, pydantic, Pillow,
│                                     # openai, python-dotenv, numpy, google-generativeai, reportlab
│                                     # (paddleocr + paddlepaddle нужны отдельно)
├─ .env.example                       # OPENAI_API_KEY
└─ ARCHITECTURE.md                    # этот файл
```

## Контракты API (текущие)

| Endpoint | Метод | Назначение |
|---|---|---|
| `/report/schema`  | GET  | вернуть текущий `ReportSchema` (JSON) |
| `/report/preview` | GET  | сгенерировать DOCX из текущего отчёта |
| `/report/preview` | POST | применить NL-правки → пересобрать DOCX (заголовки `X-Report-*`) |
| `/report/reset`   | POST | сбросить отчёт к дамми-данным |

## Контракты данных

- **`ReportSchema`** (`src/models/report.py`): `metadata`, `client`, `location`, `executive_summary`, `sections[]`, `issues[]`, `next_steps[]`. У `ReportIssue` есть `severity` (low/medium/high/critical) и опциональный `image_path` — туда логично класть путь к фото для каждой найденной проблемы.
- **OCR/GPS JSON** (выхлоп `extract_gps_paddle_v2.py`, см. `out/gps_paddle_mobile/*.json`): `image`, `source_path`, `gps.lat/lon` (`value`, `raw`, `format`), `bands.{top,bottom}_band.{raw_lines, parsed, validated_austria}`, `overall_flag` ∈ {`GPS_HIGH`, `GPS_LOW`, `NO_GPS`}. По умолчанию валидируется зона Австрии.

## Что ещё не сшито

1. **Скрипты ↔ FastAPI**: `extract_gps_*` живут как CLI; нет роутера, который принимает upload, гоняет OCR и кормит результат в `ReportSchema`.
2. **Хранилище фото**: пока нет ни директории `uploads/`, ни логики имя/хэш/дедуп (шаг 2).
3. **YOLO** (шаг 4): модели и сервиса нет.
4. **Карта** (шаг 5): только табличная сводка, не визуализация.
5. **QA-слой** (шаг 7): нет автоматической проверки сгенерированного отчёта.
6. **Связка фото → issue.image_path**: модель уже поддерживает, но не заполняется автоматически.

## Запуск (dev)

```bash
# backend (из корня)
pip install -r requirements.txt
python -m src.main           # → http://127.0.0.1:8000

# frontend
cd frontend && npm install && npm run dev   # → http://localhost:3000
```

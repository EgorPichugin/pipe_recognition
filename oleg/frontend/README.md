# Inspection AI — frontend

Nuxt 3 + Vue 3 + Tailwind. Dark-mode hackathon landing for the inspection-report pipeline.

## Quick start

```bash
# from repo root
cd frontend
npm install
npm run dev
```

Then open http://localhost:3000.

The frontend expects the FastAPI backend on `http://127.0.0.1:8000`. In dev, Nitro proxies
`/report/*` → backend, so no CORS setup is needed.

Run the backend in a second terminal:

```bash
# from repo root
pip install -r requirements.txt
python -m src.main
```

## Structure

```
frontend/
├─ app.vue                       # root
├─ pages/
│  └─ index.vue                  # composes all sections
├─ components/
│  ├─ SiteNav.vue                # sticky top nav
│  ├─ HeroSection.vue            # name + pitch + stat strip
│  ├─ ArchitectureSection.vue    # 7-stage pipeline diagram
│  ├─ Arrow.vue / ArrowFan.vue   # SVG connectors
│  ├─ MetricsSection.vue         # 4 metric cards + service status
│  ├─ InputSection.vue           # picture + requirements → POST /report/preview
│  ├─ OutputSection.vue          # renders GET /report/schema
│  └─ SiteFooter.vue
├─ composables/
│  └─ useReportApi.ts            # typed fetch wrappers + ReportSchema type
├─ assets/css/main.css           # Tailwind + design tokens
├─ tailwind.config.ts            # colors, fonts, animations
└─ nuxt.config.ts                # devProxy to FastAPI
```

## Backend endpoints used

| Endpoint                | Method | Section            |
|-------------------------|--------|--------------------|
| `/report/schema`        | GET    | OutputSection      |
| `/report/preview`       | GET    | OutputSection (download) |
| `/report/preview`       | POST   | InputSection       |
| `/report/reset`         | POST   | OutputSection (reset button) |

## Production build

```bash
npm run build
node .output/server/index.mjs
```

Set `NUXT_PUBLIC_API_BASE=https://your-backend` to point at a deployed FastAPI.

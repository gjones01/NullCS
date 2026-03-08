# NullCS

Evidence-first demo analysis UI and pipeline for CS demo forensics research.

## Prerequisites

- Python 3.10+ with `python`/`pip` on PATH
- Node.js 18+ with `npm` on PATH
- Git

## Quickstart (Backend + Frontend)

From repo root:

```powershell
python -m pip install -r main/ui/api/requirements.txt
python -m uvicorn main.ui.api.main:app --host 127.0.0.1 --port 8000 --reload
```

In a second terminal:

```powershell
cd main/ui/web
npm install
npm run dev -- --host 0.0.0.0 --port 5173
```

Use your Network URL (for example, `http://192.168.x.x:5173`) instead of localhost.
Open the Network URL printed by Vite.

## Frontend Env

Frontend API base is configured via `main/ui/web/.env.local`:

```dotenv
VITE_API_BASE_URL=/api
```

Copy from `main/ui/web/.env.example`.

## Dev Proxy

Vite proxies `/api` to `http://127.0.0.1:8000`, so the browser stays on the frontend origin.
CORS is not required in local dev when using this proxy.

## Convenience Script

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_dev.ps1
```

Add `-StartTerminals` to open backend/frontend terminals automatically.

## Smoke Test

```powershell
powershell -ExecutionPolicy Bypass -File main/scripts/smoke_ui_pipeline.ps1 -DemoPath "<path-to-demo.dem>"
```

## Docs

- UI/API details: `main/ui/README.md`
- Dev setup + change summary: `docs/dev_setup.md`

# Dev Setup Changes (PR Summary)

## Scope

This change removes hardcoded localhost usage in app code, standardizes frontend API access, aligns backend routes to `/api`, adds local dev proxying, and updates setup docs/scripts.

Inference pipeline behavior and model flow are unchanged.

## Frontend Changes

- Added `main/ui/web/.env.example` with:
  - `VITE_API_BASE_URL=/api`
- Added `main/ui/web/src/config.ts` to centralize:
  - app name: `NullCS`
  - API base path: `/api`
  - environment flags: `isDev`, `isProd`
- Added `main/ui/web/src/lib/api.ts` as the single frontend API client module.
- Removed `main/ui/web/src/api.ts`.
- Updated imports in:
  - `main/ui/web/src/App.tsx`
  - `main/ui/web/src/components/EvidenceTabs.tsx`
  - `main/ui/web/src/components/ReasonsPanel.tsx`
- Updated `main/ui/web/vite.config.ts` dev proxy:
  - `/api` -> `http://127.0.0.1:8000`

## Backend Changes

- Updated `main/ui/api/main.py`:
  - Added `GET /` root banner response.
  - Added router prefix via `APIRouter(prefix="/api")`.
  - Moved UI API endpoints under `/api/...`.
  - Added `GET /api/health` returning:
    - `status`
    - `version`
    - `model_artifact`
- Removed dev CORS middleware from app logic:
  - Not needed for local UI flow when Vite proxy is used.

## Scripts

- Added `scripts/run_dev.ps1`:
  - Prints exact backend/frontend commands.
  - Optional `-StartTerminals` opens two PowerShell windows.
- Added optional `scripts/run_dev.sh` (command print helper for mac/linux).

## Docs Updated

- Updated `README.md` quickstart:
  - Backend: `python -m uvicorn main.ui.api.main:app --host 127.0.0.1 --port 8000 --reload`
  - Frontend: `npm run dev -- --host 0.0.0.0 --port 5173`
  - Added explicit note:
    - `Open the Network URL printed by Vite.`
    - `Use your Network URL (e.g. http://192.168.x.x:5173) instead of localhost.`
- Updated `main/ui/README.md` with `/api` endpoints and proxy/env workflow.

## Ignore Rules

Updated `.gitignore` with explicit entries for:

- `.env.local` files
- logs
- frontend build/local artifacts
- local demo upload artifacts

## End-to-End Flow (unchanged behavior)

1. Upload `.dem` via UI (`/api/upload-demo`)
2. Run inference (`/api/demo/{demo_id}/run`)
3. Render players/results (`/api/demo/{demo_id}/players`)
4. Analyze player and render reason/evidence tabs (`/api/demo/{demo_id}/player/{steamid}/...`)

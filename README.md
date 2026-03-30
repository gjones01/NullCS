# NullCS

NullCS is a Counter-Strike demo review pipeline with:

- local/private inference for full analysis
- a public-safe web UI path for demo-mode deployments
- an encounter-model branch that now includes a temporal CNN baseline for stacked player scoring

## Local Development

Backend:

```powershell
python -m pip install -r main/ui/api/requirements.txt
python -m uvicorn main.ui.api.main:app --host 127.0.0.1 --port 8000 --reload
```

Frontend:

```powershell
cd main/ui/web
npm install
npm run dev -- --host 0.0.0.0 --port 5173
```

## Key Docs

- Security policy: `SECURITY.md`
- Security controls summary: `docs/security.md`
- Deployment guide: `docs/deployment.md`
- UI details: `main/ui/README.md`
- Temporal CNN experiment notes: `docs/cnn_experiments.md`

## Public Repo Rules

- Do not commit raw demos, datasets, processed outputs, model binaries, reports, logs, or secrets.
- Public deployments should use demo mode only.
- Full inference, uploads, and model artifacts should remain local or on a private backend.

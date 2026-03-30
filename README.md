# NullCS

NullCS is a Counter-Strike demo review pipeline with:

- local/private inference for full analysis
- a public-safe web UI path for demo-mode deployments
- a stacked encounter-model research path that now includes both an MLP baseline and a temporal CNN experiment

NullCS is a research project focused on single-match behavioral review, not automated enforcement. The public website is planned to launch this summer as a research preview.

## Current Snapshot

- Legit benchmark slices are currently very quiet in held-out normal and pro stress-test demos.
- Cheater benchmark slices surface strongly enough to support triage, but the system is still framed as review support rather than a verdict engine.
- The current strongest direction is the stacked player-level model with hard-negative legit data. The temporal CNN remains valuable R&D infrastructure, but it is not the current champion.

## Research Notes

- Benchmark summary and public-safe plots: `docs/research_snapshot.md`
- Temporal CNN experiment notes: `docs/cnn_experiments.md`

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
- Research snapshot: `docs/research_snapshot.md`
- Temporal CNN experiment notes: `docs/cnn_experiments.md`

## Public Repo Rules

- Do not commit raw demos, datasets, processed outputs, model binaries, reports, logs, or secrets.
- Public deployments should use demo mode only.
- Full inference, uploads, and model artifacts should remain local or on a private backend.

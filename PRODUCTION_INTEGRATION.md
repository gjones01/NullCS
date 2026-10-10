# NullCS website inference integration

> Product update (2026-10-08): the website `/analyze` entry now points to the downloadable local client. The hosted inference implementation below is retained but is not the primary public workflow. See [DESKTOP_RELEASE.md](DESKTOP_RELEASE.md) for the active desktop architecture and release gates.

The repository implements live analysis at `/analyze`. No production Python host has been provisioned. The Vercel website needs a separately deployed, persistent Python worker before live production analysis can operate. Missing gateway configuration produces an explicit unavailable message; the existing research pages remain usable.

## Architecture and ownership

1. The browser sends only `{filename, size}` to the Next.js `/api/analysis` gateway. It establishes a signed, HttpOnly, SameSite=Strict browser ownership cookie (30-day expiry).
2. Next.js authenticates to FastAPI using a server-only shared key and the verified owner ID. FastAPI persists a server-generated job ID and a hashed, expiring, single-use upload capability in SQLite.
3. The browser streams the `.dem` directly to the worker's HTTPS `PUT /api/analysis/{job}/upload`, using the capability in its Authorization header. Demo bytes never pass through a Vercel function. No Supabase service or storage credentials are required by this implementation.
4. The worker writes private `.partial` storage, checks actual length and CS2 header, hashes the upload, atomically renames it, and queues the job. Default maximum is 1 GiB. Client filenames are display metadata only; clients cannot choose storage keys or filesystem paths.
5. A single executor invokes the existing research CLI and persists a public result snapshot. Next.js proxies only allowlisted, owned status/results/explanation/evidence JSON. Model inference runs outside HTTP handlers.

This is anonymous **browser-session ownership**, not account authentication. Another browser cannot enumerate or retrieve the job by knowing its ID. Losing/expiring the cookie loses access; there is no cross-device recovery. Before broad public release, decide whether account authentication, operator admission, and/or additional ingress abuse controls are required. CORS is only a browser restriction; the gateway key and job capability enforce backend authorization.

## Canonical boundary and research integrity

`main/ui/api/pipeline_runtime.py::inference_command` launches `main/scripts/run_infer_pipeline.py --dem_path <server path> --demo_id <server ID> --out_dir <dedicated processed root>`, with the existing optional model override. `pipeline_child.py` supervises parent lifetime and runs that same entry point. Both `NULLCS_UPLOAD_DIR` and `CLARITY_PROCESSED_DIR` are passed to child processes so temporal lookup uses the same data tree.

The CLI changes are four explicit stage log messages. Feature definitions/order/hash, the 449-feature contract, aggregation, encounters/windows, temporal construction, model weights/selection, calibration, thresholds, and research scoring remain unchanged. No models were retrained and no LLM was added. Production follows the canonical CSV's risk ranking, including its tie order; it does not apply the legacy desktop API's additional display reordering. Existing interpretation/evidence functions are reused.

Each job loads models through the existing CLI. The parser still runs for both initial features and temporal loading. No speculative model cache, parser optimization, or dependency upgrade was introduced. The worker rejects the stale generated desktop executable as a production runtime.

Backend `.env` files now load before shared path constants are imported, so evidence loaders and the worker agree on configured storage roots. This integration fix does not change feature or model behavior.

## Lifecycle, failures, and persistence

| State/stage | Actual trigger |
|---|---|
| `upload_pending` | Durable reservation created |
| `uploading` | Valid capability atomically claimed |
| `queued` | Entire replay validated and saved |
| `running / preparing` | Executor starts the research process |
| `parsing` | CLI enters demoparser2 loading |
| `feature_processing` | Parsed tables are available; feature construction starts |
| `inference` | Temporal model feature step starts |
| `scoring` | Player scoring starts |
| `results_ready` | CLI exits successfully and structured results are published |
| `failed` | Upload, parsing, model, feature, scoring, publication, timeout, or interruption failure |

Only upload byte transfer has a percentage. Analysis stages come from explicit events, never elapsed-time estimates. Explanation state is separate: `unavailable -> queued -> running -> ready/failed`. The explanation CLI is `main/scripts/explain_demo.py --demo <job> --steamid <player> --mode infer`. Failed explanations do not remove ranked results and may be retried.

SQLite stores owners, jobs, upload-ticket hashes, events, and explanation states. Artifacts remain in private storage; public snapshots are `reports/<job>/web_result.json` and `<steamid>/web_explanation.json`. Atomic snapshot replacement prevents partially written JSON from appearing ready. The single process lock and serial executor protect the canonical global ranking CSV's read/rewrite behavior. **Run exactly one worker process/replica per data directory; never run research CLIs against that directory concurrently.**

Startup marks interrupted uploads/inference/explanations failed; queued work survives restart. The parent pipe watchdog terminates orphan research children. CLI timeouts kill the child. Pending reservations expire. Upload failure removes partial data where the filesystem permits it. Completed and failed analysis artifacts are retained for diagnosis; no automatic retention period or user deletion policy has been invented. Monitor disk use, back up SQLite and artifacts consistently, and define retention before public operation. The free-space floor is an admission guard, not a proof that every demo's intermediate files fit.

## Public contract

Schema version: `nullcs.analysis.v1`. Status includes job ID, stage/state, demo filename, event timestamps, measured runtime and safe error code/message. Results include:

- Demo filename/size/map and parser provenance.
- Canonical ranked players, string Steam IDs/names, `rank`, raw `model_score`, nullable `calibrated_probability`, existing adjusted `risk`, evidence confidence and feature/interpretation summaries.
- Per-player explanation state, warnings, model artifact basename and SHA-256/feature-list hash.
- Separate generated explanations and allowlisted evidence tables (first 2,000 rows; explicit truncation indicator).

Calibrated probability is `null` when the selected model lacks its own calibrator. No replacement calibration is manufactured. Internal paths, raw feature debug traces, private logs, owner IDs, ticket hashes and shared secrets are not returned. Player names and metadata render as React text. Raw parser/model diagnostics remain in worker logs.

The gateway supports reservation/capabilities, `{job}/status`, `{job}/results`, and `{job}/players/{steamid}/{explain,explanation,evidence/<filename>}` only. It cannot proxy arbitrary backend paths or uploads. POST requests require the exact website Origin. The worker disables legacy demo-list/upload/result routes in website mode to prevent bypassing ownership checks.

## Deployment

Keep Next.js on Vercel (`main/ui/site`). Deploy FastAPI on a separately managed host/container with HTTPS ingress, persistent local disk, and Python **3.13** (validated locally on 3.13.5). Install `main/ui/api/requirements-worker.txt`, preserving existing pins; its only additional explicit dependency is `joblib==1.5.3`, already used by the saved artifact loaders and present in the validated environment.

The measured local inference runtime uses CPU PyTorch. GPU is not required for functionality. Production CPU throughput, memory capacity, concurrency and hosting limits must be measured on the chosen host. Use one executor initially. SQLite WAL and the output lock require a local filesystem with working locking; do not place this data tree on an untested network filesystem.

Provision a private persistent directory with `uploads/`, `processed/` and `state/`. Copy the selected model bundle to `processed/models/`, preserving its artifact names. For the verified default bundle:

```text
xgb_player_level_cs2cd.json
xgb_player_level_cs2cd_features.txt
xgb_player_level_cs2cd_training_manifest.json
xgb_player_level_cs2cd_calibration.pkl
encounter_nn_cs2cd.pt
encounter_nn_cs2cd_features.json
encounter_nn_cs2cd_preproc.pkl
encounter_nn_cs2cd_training_manifest.json
```

Preserve the corresponding bundle/manifest if intentionally selecting a rank variant or other supported override; a rank-selected model may legitimately have no calibrator. Do not substitute the absent `encounter_nn_cs2cd_temporal_seq32.pt`. Model artifacts are not embedded in the image or committed by this change.

Native startup, from the repository root with worker variables set:

```sh
python -m pip install -r main/ui/api/requirements-worker.txt
python -m uvicorn main.ui.api.main:app --host 0.0.0.0 --port 8000 --workers 1 --no-proxy-headers --timeout-graceful-shutdown 15
```

Container build definition: `main/ui/api/Dockerfile.worker` (not the pre-existing demo-mode root Dockerfile/Compose setup). Build from the repository root:

```sh
docker build -f main/ui/api/Dockerfile.worker -t nullcs-worker .
```

Mount the dedicated persistent volume at `/data`, writable by UID 10001. The image runs without root, includes `libgomp1`, excludes unrelated repository/data/secrets from its build context, and supplies the packaged root marker required by existing path resolution. Supply the key and exact frontend origin at runtime. Prefer a read-only model bind mount at `/data/processed/models`. Do not expose the data volume as static files.

Health check: authenticated `GET /api/health`; check `upload_enabled`. It confirms executor availability, not model correctness or throughput. Perform the real demo acceptance check below before routing public traffic. Terminate HTTPS at the chosen ingress and forward to port 8000. Allow a 1 GiB request and at least the configured upload duration, with streaming/request buffering configured appropriately. Next.js must be able to reach the worker control API; browsers must reach its public upload URL. Configure CORS for `https://www.nullcs.app`. No production hostname has been invented or provisioned.

## Environment variables

Templates: `main/ui/site/.env.example` and `main/ui/api/.env.example`. Generate independent random secrets of at least 32 characters; never commit values.

| Variable | Component / exposure | Purpose |
|---|---|---|
| `NULLCS_API_BASE_URL` | Next.js server only | Worker origin for small control requests |
| `NULLCS_WORKER_PUBLIC_URL` | Next.js config; returned URL is public | Browser-reachable HTTPS worker origin; defaults to API origin |
| `NULLCS_API_KEY` | Next.js + worker; secret | Shared gateway authentication |
| `NULLCS_SESSION_SECRET` | Next.js server only; secret | Signs browser ownership cookies; rotation invalidates sessions |
| `NULLCS_WEB_ANALYSIS=1` | Worker only | Enables private website jobs and disables legacy routes |
| `NULLCS_ENV=production` | Worker only | Production error/auth behavior |
| `NULLCS_DEMO_MODE=0` | Worker only | Required for real inference |
| `NULLCS_FRONTEND_ORIGIN` | Worker config; public origin | Exact allowed website origin |
| `NULLCS_UPLOAD_DIR` | Worker only | Dedicated private upload volume |
| `CLARITY_PROCESSED_DIR` | Worker only | Dedicated artifacts/models/reports volume; research default is rejected |
| `NULLCS_WEB_STATE_DIR` | Worker only | SQLite state; default sibling `web_state` |
| `NULLCS_PROJECT_ROOT`, `CLARITY_PYTHON_EXE` | Worker only | Optional explicit repository/runtime locations |
| `NULLCS_MODEL_ARTIFACT` / `CLARITY_MODEL_ARTIFACT` | Worker only | Existing optional model override |
| `NULLCS_WEB_MAX_UPLOAD_BYTES` | Worker config; limit public | Default 1073741824 bytes |
| `NULLCS_WEB_UPLOAD_TIMEOUT_SECONDS` | Worker only | Upload/reservation lifetime; default 1800 |
| `NULLCS_WEB_MAX_PENDING_JOBS` | Worker only | Global pending cap, default 8; also two active jobs per owner |
| `NULLCS_WEB_MIN_FREE_BYTES` | Worker only | Default 2147483648-byte free-space floor |
| `NULLCS_JOB_TIMEOUT_SECONDS` | Worker only | Inference timeout, default 1800 |
| `NULLCS_EXPLAIN_TIMEOUT_SECONDS` | Worker only | Explanation timeout, default 120 |
| `NULLCS_REQUEST_TIMEOUT_SECONDS` | Worker only | Small control request timeout, default 30 |
| `NULLCS_RATE_LIMIT_CAPACITY`, `NULLCS_RATE_LIMIT_REFILL_PER_SECOND` | Worker only | Request token bucket, defaults 30 and 0.5 |

All analysis secrets lack the `NEXT_PUBLIC_` prefix. Existing `NEXT_PUBLIC_SUPABASE_*` placeholders are unused by this flow. No service-role credential belongs in the browser. Locally, use site `http://localhost:3001`, API/public worker `http://127.0.0.1:8001`, and matching worker CORS. Use HTTPS origins in production. `.env.example` is a template, not a source of live credentials.

## Validation and release gate

```sh
python -B -m pytest main/ui/api/tests/test_config.py main/ui/api/tests/test_security.py main/ui/api/tests/test_analysis.py main/ui/api/tests/test_parser_required_columns.py main/ui/api/tests/test_pipeline_child.py -q -p no:cacheprovider
python -B main/scripts/check_parser_contract.py
python -B main/scripts/check_web_integration.py --site http://localhost:3001 --demo <real-demo.dem> --repeat 2 --json-out <private-output.json>
# In main/ui/site:
node --experimental-strip-types --test tests/analysis-security.test.mjs
npx tsc --noEmit --incremental false
npm run build
```

The HTTP acceptance script uses the real website gateway, direct upload, canonical models, persistence, access-control checks, separate explanations, and actual evidence. It compares repeat ranked outputs and provenance without seeding/changing research behavior. Browser verification additionally checks rendered player/evidence tables. Keep reports/screenshots/demo copies in ignored private storage.

Linux CPython 3.13 wheel metadata resolution passed for the pinned requirements using pip's cross-platform dry run. This is **not** a built-container test: Windows-host environment markers can differ from Linux, and CUDA-related dependencies/native libraries must still be checked inside the image. Docker is unavailable in the validation environment. Before deployment, build the image, load both model artifacts/calibrator, run the parser sentinel and a real demo inside it, then measure resource usage and verify volume/restart/HTTPS ingress behavior.

### Observed local results (2026-10-06)

- 50 Python tests passed: the existing four security tests, 22 required-column rejection cases, transport/ownership/failure/lifecycle checks, real missing-model CLI failure, model-import and parent-death watchdog checks, and environment-file path consistency. Only the existing Starlette/httpx deprecation warning appeared.
- Both Node gateway security tests passed. TypeScript and the optimized Next.js production build passed. Browser bundles contained neither local validation secret.
- The patch-14153 sentinel passed its full production guard: 1,089,620 tick rows, with the same two decorative-field warnings.
- Real `TEST_20260501_102349_02b8afde.dem` (232,415,622 bytes; de_inferno) entered through the browser, uploaded directly to port 8001, ran the canonical models, persisted results, and displayed all ten ranked players. Separate explanations produced four tables; the top player's reaction-time table had 20 rows and smoke table three rows (two other tables legitimately empty). Browser console checks found no errors.
- Two fresh complete HTTP runs through Next.js and the worker had exactly equal player ordering, raw/calibrated/review scores, confidence, model hashes, and parser provenance. This establishes repeatability for that fixture/runtime, not universal determinism across hardware or parser versions.
- Measured inference times were 38.25 and 35.46 seconds for those two runs; complete HTTP checks including upload/polling/explanation/evidence took 46.59 and 43.02 seconds. The final browser run took 34.9 seconds for inference; an earlier browser run took 50.6 seconds. These are local observations, not before/after optimization claims or production capacity estimates.
- On the local i5-13400F / approximately 32 GiB Windows machine with CPU PyTorch, a sampled inference process reported a peak working set of 2,073,485,312 bytes (approximately 1.93 GiB). This is not a recommended memory limit or a worst-case bound for larger demos.
- A valid-header but corrupt 32-byte demo failed through the real website/API path with `parser_failed`, without exposing a traceback/path. An interrupted job became `worker_restarted` on startup. Upload cleanup errors, process timeout, duplicate capabilities, capacity, unauthorized access, and fair explanation scheduling have focused tests.
- After restarting the worker, the browser's existing owner session still retrieved all ten persisted players and a `ready` explanation. The existing homepage also loaded without browser errors.
- The real `xgb_player_level_cs2cd_ranksel_base` model scored the fixture's actual extracted features into ten players with all calibrated probabilities absent. The normal model/calibrator loaded through every complete run and retained its version warning.
- The XGBoost hash remains `f9016d95a144e1004f40c01f15b86879d9d9101cdda4659acaa261ac80610ea8`; the 449-feature-list hash remains `26dfc64615695c1bac225b37eb42cd0efa72a0247c4af685b64da29ae42a58e4`.

Private reproducibility artifacts are under ignored `main/data/web_validation/` (HTTP report, parser check, logs, snapshots, screenshots, memory samples and wheel metadata). They must not be committed or exposed as static content.

### Reliability follow-up (2026-10-07)

Review of the existing tree found one explanation recovery gap: a lost or corrupt completed explanation snapshot left its state at `ready`, preventing regeneration. The owned explanation endpoint now records `failed`, returns a safe retryable error, and preserves ranked results. Three additional cases cover missing/corrupt snapshots and actual explanation CLI failure with absent inputs. `python -B -m pytest main/ui/api/tests/test_analysis.py main/ui/api/tests/test_security.py -q -p no:cacheprovider` passed all **28 targeted tests**. The previous successful full-pipeline runs were retained, not repeated. Production hosting and actual container execution remain external blockers.

## Remaining known limitations

- `demoparser2==0.41.4` has the upstream stale user-command issue (LaihoE/demoparser issue 340). The passing patch-14153 schema sentinel cannot prove those values are semantically fresh. No speculative parser change was made.
- The saved sklearn calibrator emits its existing 1.7.1-to-1.9.0 serialization warning. Artifact behavior is preserved and the UI warns; rank variants without calibration remain explicitly uncalibrated.
- Existing explanation reason summaries may use different evidence subsets from the scoring signal values. They are exposed as the existing research explanations; no feature/formula reconciliation was silently performed.
- Historical paths, the stale desktop executable, and unrelated audit issues remain outside this integration. The new worker uses dedicated configured paths and the Python CLI.
- Retention/deletion policy, account requirements, public abuse protection, production capacity, actual container execution, and production HTTPS deployment remain operator decisions/acceptance checks.

The future investigation/agent integration point is the owned `nullcs.analysis.v1` result plus per-player explanation/evidence endpoints. An agent can consume that evidence later without entering or changing the classification/ranking path. No agent layer is implemented.

from __future__ import annotations

import asyncio
import datetime as dt
import json
import logging
import re
import subprocess
import threading
import time
import uuid
from pathlib import Path
import sys

import pandas as pd
from fastapi import APIRouter, Body, FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import (
    APP_MODE,
    APP_ENV,
    DEMO_MODE,
    ENABLE_DIAGNOSTICS,
    EXPLAIN_TIMEOUT_SECONDS,
    FRONTEND_ORIGIN,
    INFER_CSV,
    IS_DESKTOP_MODE,
    IS_PRODUCTION,
    JOBS_PATH,
    JOB_TIMEOUT_SECONDS,
    MAX_UPLOAD_BYTES,
    MODEL_ARTIFACT,
    NULLCS_API_KEY,
    NULLCS_DESKTOP_KEY,
    PIPELINE_EXE,
    PROCESSED_DIR,
    PROJECT_ROOT,
    PYTHON_EXE,
    RATE_LIMIT_CAPACITY,
    RATE_LIMIT_REFILL_PER_SECOND,
    REPORTS_DIR,
    REQUEST_TIMEOUT_SECONDS,
    SCRIPTS_DIR,
    STATE_DIR,
    UPLOAD_DIR,
    model_version_label,
)
from main.src.utils.model_registry import resolve_model_artifacts
from main.src.utils.behavioral_context import build_demo_interpretations, interpretation_from_summary, load_demo_frames, build_demo_player_summary

APP_VERSION = "0.3.0"
PUBLIC_PATHS = {"/"}
PIPELINE_STEPS = ["Uploading", "Parsing", "Feature Build", "Model", "Explanation"]
SAFE_SEGMENT_RE = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
SAFE_FILENAME_RE = re.compile(r"^evidence_[A-Za-z0-9_-]{1,80}\.csv$")
BANNED_MAGIC_PREFIXES = (
    b"MZ",
    b"PK\x03\x04",
    b"PK\x05\x06",
    b"PK\x07\x08",
    b"7z\xbc\xaf\x27\x1c",
    b"Rar!\x1a\x07\x00",
    b"Rar!\x1a\x07\x01\x00",
    b"\x7fELF",
    b"\xfe\xed\xfa\xce",
    b"\xfe\xed\xfa\xcf",
    b"\xcf\xfa\xed\xfe",
    b"\xca\xfe\xba\xbe",
)

logger = logging.getLogger("nullcs.api")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


def _allowed_origins() -> list[str]:
    if IS_PRODUCTION:
        return [FRONTEND_ORIGIN] if FRONTEND_ORIGIN else []
    origins = [
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "http://tauri.localhost",
        "https://tauri.localhost",
        "tauri://localhost",
        "http://localhost",
        "http://127.0.0.1",
    ]
    if FRONTEND_ORIGIN:
        origins.append(FRONTEND_ORIGIN)
    return origins


app = FastAPI(
    title="NullCS UI API",
    version=APP_VERSION,
    docs_url=None if (IS_PRODUCTION or IS_DESKTOP_MODE) else "/docs",
    redoc_url=None if (IS_PRODUCTION or IS_DESKTOP_MODE) else "/redoc",
    openapi_url=None if (IS_PRODUCTION or IS_DESKTOP_MODE) else "/openapi.json",
)
api = APIRouter(prefix="/api")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins(),
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-NULLCS-KEY"],
)

_jobs_lock = threading.Lock()


class TokenBucketLimiter:
    def __init__(self, capacity: int, refill_per_second: float) -> None:
        self.capacity = max(1, capacity)
        self.refill_per_second = max(0.01, refill_per_second)
        self._buckets: dict[str, tuple[float, float]] = {}
        self._lock = threading.Lock()

    def allow(self, key: str) -> tuple[bool, int]:
        now = time.monotonic()
        with self._lock:
            tokens, last = self._buckets.get(key, (float(self.capacity), now))
            tokens = min(self.capacity, tokens + (now - last) * self.refill_per_second)
            if tokens < 1.0:
                wait_seconds = max(1, int((1.0 - tokens) / self.refill_per_second))
                self._buckets[key] = (tokens, now)
                return False, wait_seconds
            self._buckets[key] = (tokens - 1.0, now)
            return True, 0


limiter = TokenBucketLimiter(RATE_LIMIT_CAPACITY, RATE_LIMIT_REFILL_PER_SECOND)


def _error_payload(message: str, code: str) -> dict[str, dict[str, str]]:
    return {"error": {"code": code, "message": message}}


def _json_error(status_code: int, message: str, code: str, headers: dict[str, str] | None = None) -> JSONResponse:
    return JSONResponse(status_code=status_code, content=_error_payload(message, code), headers=headers)


def _now() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


def _demo_id() -> str:
    ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"TEST_{ts}_{uuid.uuid4().hex[:8]}"


def _sanitize_segment(value: str, field_name: str) -> str:
    val = str(value or "").strip()
    if not SAFE_SEGMENT_RE.fullmatch(val):
        raise HTTPException(status_code=400, detail=f"Invalid {field_name}")
    return val


def _sanitize_log_text(text: str) -> str:
    sanitized = str(text or "")
    replacements = [
        (str(PROJECT_ROOT), "<project-root>"),
        (str(PROCESSED_DIR), "<processed-dir>"),
        (str(REPORTS_DIR), "<reports-dir>"),
        (str(UPLOAD_DIR), "<upload-dir>"),
    ]
    for src, dst in replacements:
        if src:
            sanitized = sanitized.replace(src, dst)
    sanitized = re.sub(r"[A-Za-z]:\\\\[^ \n\r\t]+", "<path>", sanitized)
    return sanitized


def _tail(path: Path, n: int = 120) -> str:
    if not path.exists():
        return ""
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    return _sanitize_log_text("\n".join(lines[-n:]))


def _load_jobs() -> dict:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    if not JOBS_PATH.exists():
        return {}
    try:
        return json.loads(JOBS_PATH.read_text(encoding="utf-8"))
    except Exception:
        logger.warning("Failed to parse jobs state; resetting in-memory view.")
        return {}


def _save_jobs(jobs: dict) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    JOBS_PATH.write_text(json.dumps(jobs, indent=2), encoding="utf-8")


def _set_job(demo_id: str, **fields) -> dict:
    with _jobs_lock:
        jobs = _load_jobs()
        cur = jobs.get(demo_id, {})
        cur.update(fields)
        cur["updated_at"] = _now()
        jobs[demo_id] = cur
        _save_jobs(jobs)
        return cur


def _get_job(demo_id: str) -> dict | None:
    with _jobs_lock:
        return _load_jobs().get(demo_id)


def _infer_pipeline_step(state: str, logs_tail: str) -> dict:
    stage_idx = 0
    txt = (logs_tail or "").lower()
    if "[info] parsed zip:" in txt:
        stage_idx = 2
    if "engagement_features.parquet" in txt:
        stage_idx = 3
    if "ranked_players_infer.csv" in txt:
        stage_idx = 4
    if state == "done":
        stage_idx = 4
    if state == "error":
        stage_idx = max(stage_idx, 1)
    stage_idx = max(0, min(stage_idx, len(PIPELINE_STEPS) - 1))
    return {"stage_index": stage_idx, "stage": PIPELINE_STEPS[stage_idx], "steps": PIPELINE_STEPS}


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    if forwarded:
        return forwarded
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def _ensure_api_key(request: Request) -> None:
    if request.method.upper() == "OPTIONS":
        return
    if request.url.path in PUBLIC_PATHS:
        return
    expected_key = NULLCS_API_KEY if IS_PRODUCTION else (NULLCS_DESKTOP_KEY if IS_DESKTOP_MODE else "")
    if not expected_key:
        if not IS_PRODUCTION and not IS_DESKTOP_MODE:
            return
        raise HTTPException(status_code=503, detail="Server authentication is not configured")
    supplied = request.headers.get("X-NULLCS-KEY", "").strip()
    if supplied != expected_key:
        raise HTTPException(status_code=401, detail="API key required")


def _ensure_rate_limit(request: Request) -> None:
    if request.method.upper() == "OPTIONS":
        return
    if not IS_PRODUCTION and not IS_DESKTOP_MODE:
        return
    if not request.url.path.startswith("/api"):
        return
    if request.url.path == "/api/health":
        return
    allowed, retry_after = limiter.allow(_client_ip(request))
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. Retry in about {retry_after} seconds.",
            headers={"Retry-After": str(retry_after)},
        )


def _sanitize_trace(value):
    if isinstance(value, dict):
        cleaned = {}
        for key, item in value.items():
            if "path" in str(key).lower():
                continue
            cleaned[key] = _sanitize_trace(item)
        return cleaned
    if isinstance(value, list):
        return [_sanitize_trace(item) for item in value]
    if isinstance(value, str):
        return _sanitize_log_text(value)
    return value


def _run_pipeline_background(demo_id: str, dem_path: Path) -> None:
    log_dir = REPORTS_DIR / demo_id / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "pipeline.log"
    cmd = [
        *([PIPELINE_EXE, "run-infer"] if PIPELINE_EXE else [str(PYTHON_EXE), "-u", str(SCRIPTS_DIR / "run_infer_pipeline.py")]),
        "--dem_path",
        str(dem_path),
        "--demo_id",
        demo_id,
        "--out_dir",
        str(PROCESSED_DIR),
    ]
    if MODEL_ARTIFACT:
        cmd.extend(["--model-artifact", MODEL_ARTIFACT])
    _set_job(demo_id, state="running", log_key="pipeline", error="", log_path=str(log_path))
    with log_path.open("a", encoding="utf-8", errors="replace") as lf:
        lf.write(f"[{_now()}] START {' '.join(cmd)}\n")
        lf.flush()
        proc = subprocess.Popen(
            cmd,
            cwd=str(PROJECT_ROOT),
            stdout=lf,
            stderr=subprocess.STDOUT,
            text=True,
        )
        _set_job(demo_id, pid=proc.pid)
        try:
            code = proc.wait(timeout=JOB_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            proc.kill()
            code = 124
            lf.write(f"\n[{_now()}] TIMEOUT after {JOB_TIMEOUT_SECONDS} seconds\n")
            lf.flush()
        lf.write(f"\n[{_now()}] EXIT_CODE {code}\n")
        lf.flush()
    if code == 0:
        _set_job(demo_id, state="done", return_code=code)
        return
    logs_tail = _tail(log_path, n=80)
    if code == 124:
        message = "Analysis job timed out"
    elif "EntityNotFound" in logs_tail or "DemoParser.Exception" in logs_tail:
        message = "The parser could not read this demo. It may be from an unsupported CS2 patch, incomplete replay download, or a demo format demoparser2 cannot currently decode."
    else:
        message = "Analysis job failed"
    _set_job(demo_id, state="error", return_code=code, error=message)


def _upload_path_for_job(demo_id: str) -> Path:
    cur = _get_job(demo_id)
    if not cur:
        raise HTTPException(status_code=404, detail="Demo job not found")
    upload_rel = str(cur.get("upload_relpath", "")).strip()
    if not upload_rel:
        raise HTTPException(status_code=404, detail="Uploaded demo not found")
    upload_path = (UPLOAD_DIR / upload_rel).resolve()
    base = UPLOAD_DIR.resolve()
    if upload_path == base or base not in upload_path.parents or not upload_path.exists():
        raise HTTPException(status_code=404, detail="Uploaded demo not found")
    return upload_path

def _source_path_for_job(cur: dict) -> Path | None:
    raw_value = str(cur.get("source_dem_path", "")).strip()
    if not raw_value:
        return None
    source_path = Path(raw_value).expanduser().resolve()
    if not source_path.exists() or not source_path.is_file() or source_path.suffix.lower() != ".dem":
        raise HTTPException(status_code=404, detail="Selected demo file not found")
    return source_path


def _safe_report_dir(demo_id: str, steamid: str) -> Path:
    safe_demo_id = _sanitize_segment(demo_id, "demo_id")
    safe_steamid = _sanitize_segment(steamid, "steamid")
    base = REPORTS_DIR.resolve()
    target = (REPORTS_DIR / safe_demo_id / safe_steamid).resolve()
    if target == base or base not in target.parents:
        raise HTTPException(status_code=400, detail="Invalid report path")
    return target


def _safe_evidence_path(demo_id: str, steamid: str, filename: str) -> Path:
    name = Path(filename).name
    if name != filename or not SAFE_FILENAME_RE.fullmatch(name):
        raise HTTPException(status_code=400, detail="Invalid evidence filename")
    path = _safe_report_dir(demo_id, steamid) / name
    if not path.exists():
        raise HTTPException(status_code=404, detail="Evidence file not found")
    return path


def _load_debug_trace(demo_id: str) -> dict:
    if not ENABLE_DIAGNOSTICS:
        raise HTTPException(status_code=404, detail="Diagnostics are disabled")
    safe_demo_id = _sanitize_segment(demo_id, "demo_id")
    debug_path = REPORTS_DIR / safe_demo_id / "debug_score_trace.json"
    if not debug_path.exists():
        raise HTTPException(status_code=404, detail="Debug trace not found")
    try:
        trace = json.loads(debug_path.read_text(encoding="utf-8"))
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to parse debug trace")
    return _sanitize_trace(trace)


def _infer_artifact_status(demo_id: str) -> dict[str, object]:
    safe_demo_id = _sanitize_segment(demo_id, "demo_id")
    report_dir = REPORTS_DIR / safe_demo_id
    infer_manifest = report_dir / "infer_manifest.json"
    ranked_players = report_dir / "ranked_players_infer.csv"
    debug_trace = report_dir / "debug_score_trace.json"
    if infer_manifest.exists() and ranked_players.exists() and debug_trace.exists():
        return {
            "state": "done",
            "error": "",
            "artifact_source": "infer_outputs",
            "artifact_updated_at": dt.datetime.fromtimestamp(max(
                infer_manifest.stat().st_mtime,
                ranked_players.stat().st_mtime,
                debug_trace.stat().st_mtime,
            )).isoformat(timespec="seconds"),
        }
    return {"state": "unknown", "error": ""}


def _pid_is_running(pid_value: object) -> bool:
    try:
        pid = int(pid_value)
    except Exception:
        return False
    if pid <= 0:
        return False
    try:
        if sys.platform.startswith("win"):
            res = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}"],
                capture_output=True,
                text=True,
                check=False,
            )
            return str(pid) in (res.stdout or "")
        res = subprocess.run(["ps", "-p", str(pid)], capture_output=True, text=True, check=False)
        return str(pid) in (res.stdout or "")
    except Exception:
        return False


def _reconcile_job_state(demo_id: str, cur: dict) -> dict:
    state = str(cur.get("state", "queued")).strip().lower()
    artifact = _infer_artifact_status(demo_id)
    if state not in {"queued", "running"} and artifact.get("state") == "done":
        if state != "done":
            cur = _set_job(
                demo_id,
                state="done",
                error="",
                return_code=0,
                artifact_source=artifact.get("artifact_source"),
                artifact_updated_at=artifact.get("artifact_updated_at"),
            )
        else:
            cur = {**cur, **artifact}
        return cur

    if state == "running" and not _pid_is_running(cur.get("pid")):
        log_path = Path(cur.get("log_path", ""))
        logs_tail = _tail(log_path)
        if "EXIT_CODE 0" in logs_tail:
            cur = _set_job(demo_id, state="done", error="", return_code=0)
        elif "EXIT_CODE" in logs_tail:
            if "EntityNotFound" in logs_tail or "DemoParser.Exception" in logs_tail:
                message = "The parser could not read this demo. It may be from an unsupported CS2 patch, incomplete replay download, or a demo format demoparser2 cannot currently decode."
            else:
                message = cur.get("error") or "Analysis job failed"
            cur = _set_job(
                demo_id,
                state="error",
                error=message,
                return_code=int(re.search(r"EXIT_CODE\s+(-?\d+)", logs_tail).group(1)) if re.search(r"EXIT_CODE\s+(-?\d+)", logs_tail) else cur.get("return_code", 1),
            )
    return cur


def _public_job_status(demo_id: str, cur: dict) -> dict:
    cur = _reconcile_job_state(demo_id, cur)
    log_path = Path(cur.get("log_path", ""))
    logs_tail = _tail(log_path)
    state = cur.get("state", "queued")
    return {
        "demo_id": demo_id,
        "state": state,
        "logs_tail": logs_tail,
        "error": cur.get("error", ""),
        "original_filename": str(cur.get("original_filename", "")),
        **_infer_pipeline_step(state, logs_tail),
    }


def _is_banned_magic(content_prefix: bytes) -> bool:
    for prefix in BANNED_MAGIC_PREFIXES:
        if content_prefix.startswith(prefix):
            return True
    return False


async def _write_validated_upload(upload: UploadFile, out_path: Path) -> int:
    total = 0
    prefix = b""
    try:
        with out_path.open("wb") as handle:
            while True:
                chunk = await upload.read(1024 * 1024)
                if not chunk:
                    break
                if len(prefix) < 16:
                    prefix = (prefix + chunk)[:16]
                    if _is_banned_magic(prefix):
                        raise HTTPException(status_code=400, detail="Archives and executable formats are not allowed")
                total += len(chunk)
                if MAX_UPLOAD_BYTES > 0 and total > MAX_UPLOAD_BYTES:
                    raise HTTPException(status_code=413, detail="Upload exceeds the configured size limit")
                handle.write(chunk)
    except Exception:
        if out_path.exists():
            out_path.unlink(missing_ok=True)
        raise
    return total


def _sanitize_table_value(value):
    try:
        if pd.isna(value):
            return None
    except Exception:
        pass
    if isinstance(value, str):
        return _sanitize_log_text(value)[:500]
    if isinstance(value, (int, float, bool)):
        return value
    return str(value)[:200]


def _sanitize_dataframe(df: pd.DataFrame) -> tuple[list[str], list[dict[str, object]]]:
    columns = [str(c)[:64] for c in df.columns.tolist()]
    rows = []
    for row in df.to_dict(orient="records"):
        rows.append({str(k)[:64]: _sanitize_table_value(v) for k, v in row.items()})
    return columns, rows


def _health_payload() -> dict[str, object]:
    model_info = _resolved_model_info() if ENABLE_DIAGNOSTICS else {"artifact_name": model_version_label()}
    return {
        "status": "ok",
        "version": app.version,
        "environment": APP_ENV,
        "mode": APP_MODE,
        "auth_required": IS_PRODUCTION or IS_DESKTOP_MODE,
        "upload_enabled": not DEMO_MODE and (IS_DESKTOP_MODE or not IS_PRODUCTION),
        "max_upload_bytes": (MAX_UPLOAD_BYTES if MAX_UPLOAD_BYTES > 0 else None),
        "model_version": model_version_label(),
        "model_info": model_info,
        "product_info": {
            "name": "NullCS",
            "identity": "Single-match behavioral review workspace",
            "tagline": "Match-relative analyst triage with explainable evidence.",
            "analyst_note": "Surface behavioral deviation, evidence confidence, and neutral next-step guidance without implying a cheating verdict.",
        },
    }


def _resolved_model_info() -> dict[str, object]:
    try:
        models_dir = PROCESSED_DIR / "models"
        model_path, _ = resolve_model_artifacts(models_dir, MODEL_ARTIFACT or None)
        manifest_path = model_path.with_name(f"{model_path.stem}_training_manifest.json")
        info: dict[str, object] = {
            "artifact_name": model_path.name,
        }
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            info.update(
                {
                    "training_mode": manifest.get("train_data_mode", "unknown"),
                    "training_timestamp": manifest.get("created_at") or manifest.get("artifact_timestamp_local"),
                    "class_balance": manifest.get("class_balance_after_n_players_filter", {}),
                    "source_stats": manifest.get("source_stats")
                    or manifest.get("aggregate_summary", {}).get("source_stats", {}),
                    "feature_count": manifest.get("feature_count"),
                }
            )
        return info
    except Exception:
        return {"artifact_name": model_version_label()}


@app.middleware("http")
async def security_middleware(request: Request, call_next):
    try:
        _ensure_rate_limit(request)
        _ensure_api_key(request)
        response = await asyncio.wait_for(call_next(request), timeout=REQUEST_TIMEOUT_SECONDS)
    except asyncio.TimeoutError:
        return _json_error(504, "Request timed out", "request_timeout")
    except HTTPException as exc:
        return await http_exception_handler(request, exc)

    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if request.url.path.startswith("/api"):
        response.headers["Cache-Control"] = "no-store"
    if IS_PRODUCTION:
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains; preload"
    return response


@app.exception_handler(HTTPException)
async def http_exception_handler(_request: Request, exc: HTTPException):
    detail = exc.detail if isinstance(exc.detail, str) else "Request failed"
    if exc.status_code >= 500 and IS_PRODUCTION:
        detail = "Server error"
    return _json_error(exc.status_code, detail, f"http_{exc.status_code}", headers=exc.headers)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_request: Request, _exc: RequestValidationError):
    return _json_error(422, "Invalid request payload", "validation_error")


@app.exception_handler(Exception)
async def unhandled_exception_handler(_request: Request, exc: Exception):
    logger.exception("Unhandled API error", exc_info=exc)
    message = "Server error" if IS_PRODUCTION else f"Server error: {exc}"
    return _json_error(500, message, "internal_error")


@app.get("/")
def root() -> dict:
    return {
        "name": "NullCS API",
        "identity": "Single-match behavioral review workspace",
        "status": "ok",
        "version": app.version,
        "health": "/api/health",
    }


@api.get("/health")
def health() -> dict[str, object]:
    return _health_payload()


@api.post("/upload-demo")
async def upload_demo(request: Request, file: UploadFile = File(...), demo_id: str | None = Form(default=None)) -> dict:
    if DEMO_MODE:
        raise HTTPException(status_code=403, detail="Public demo mode does not accept uploads")

    filename = str(file.filename or "").strip()
    if Path(filename).name != filename:
        raise HTTPException(status_code=400, detail="Invalid upload filename")
    if not filename.lower().endswith(".dem"):
        raise HTTPException(status_code=400, detail="Only .dem uploads are supported")

    safe_demo_id = _sanitize_segment(demo_id, "demo_id") if demo_id else _demo_id()
    upload_token = uuid.uuid4().hex
    out_dir = UPLOAD_DIR / safe_demo_id
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{upload_token}.dem"
    size_bytes = await _write_validated_upload(file, out_path)

    _set_job(
        safe_demo_id,
        state="queued",
        upload_relpath=f"{safe_demo_id}/{upload_token}.dem",
        upload_size_bytes=size_bytes,
        uploader_ip=_client_ip(request),
        original_filename=filename,
        error="",
    )
    return {"demo_id": safe_demo_id, "original_filename": filename}


@api.post("/demo/from-path")
def queue_demo_from_path(
    request: Request,
    payload: dict = Body(...),
) -> dict:
    if DEMO_MODE:
        raise HTTPException(status_code=403, detail="Public demo mode does not run analysis jobs")
    if not IS_DESKTOP_MODE:
        raise HTTPException(status_code=403, detail="Local-path demo intake is only available in desktop mode")

    raw_path = str(payload.get("path", "")).strip()
    if not raw_path:
        raise HTTPException(status_code=400, detail="Missing local demo path")
    dem_path = Path(raw_path).expanduser().resolve()
    if not dem_path.exists() or not dem_path.is_file() or dem_path.suffix.lower() != ".dem":
        raise HTTPException(status_code=400, detail="Expected an existing local .dem file")

    try:
        size_bytes = int(dem_path.stat().st_size)
    except OSError:
        raise HTTPException(status_code=400, detail="Unable to read the selected demo file")
    if MAX_UPLOAD_BYTES > 0 and size_bytes > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Selected demo exceeds the configured size limit")
    try:
        with dem_path.open("rb") as handle:
            if _is_banned_magic(handle.read(16)):
                raise HTTPException(status_code=400, detail="Archives and executable formats are not allowed")
    except HTTPException:
        raise
    except OSError:
        raise HTTPException(status_code=400, detail="Unable to read the selected demo file")

    requested_demo_id = payload.get("demo_id")
    safe_demo_id = _sanitize_segment(requested_demo_id, "demo_id") if requested_demo_id else _demo_id()
    _set_job(
        safe_demo_id,
        state="queued",
        source_dem_path=str(dem_path),
        upload_size_bytes=size_bytes,
        uploader_ip=_client_ip(request),
        original_filename=dem_path.name,
        error="",
    )
    cur = _reconcile_job_state(safe_demo_id, _get_job(safe_demo_id) or {})
    if str(cur.get("state", "")).lower() == "done":
        return {"demo_id": safe_demo_id, "state": "done", "original_filename": dem_path.name}
    if cur.get("state") == "running":
        return {"demo_id": safe_demo_id, "state": "running", "original_filename": dem_path.name}

    thread = threading.Thread(target=_run_pipeline_background, args=(safe_demo_id, dem_path), daemon=True)
    thread.start()
    return {"demo_id": safe_demo_id, "state": "queued", "original_filename": dem_path.name}


@api.post("/demo/{demo_id}/run")
def run_demo(demo_id: str) -> dict:
    if DEMO_MODE:
        raise HTTPException(status_code=403, detail="Public demo mode does not run analysis jobs")

    safe_demo_id = _sanitize_segment(demo_id, "demo_id")
    cur = _reconcile_job_state(safe_demo_id, _get_job(safe_demo_id) or {})
    if str(cur.get("state", "")).lower() == "done":
        return {"demo_id": safe_demo_id, "state": "done"}
    if cur.get("state") == "running":
        return {"demo_id": safe_demo_id, "state": "running"}

    dem_path = _source_path_for_job(cur) or _upload_path_for_job(safe_demo_id)

    _set_job(safe_demo_id, state="queued", error="")
    thread = threading.Thread(target=_run_pipeline_background, args=(safe_demo_id, dem_path), daemon=True)
    thread.start()
    return {"demo_id": safe_demo_id, "state": "queued"}


@api.get("/demo/{demo_id}/status")
def demo_status(demo_id: str) -> dict:
    safe_demo_id = _sanitize_segment(demo_id, "demo_id")
    cur = _get_job(safe_demo_id)
    if not cur:
        raise HTTPException(status_code=404, detail="Demo job not found")
    return _public_job_status(safe_demo_id, cur)


def _clamp01(value: float | int | None) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except Exception:
        return 0.0


def _coalesce_metric(row: pd.Series | dict, *names: str) -> float | None:
    for name in names:
        try:
            value = row.get(name) if isinstance(row, dict) else row.get(name)
        except Exception:
            value = None
        if value is None:
            continue
        try:
            if pd.isna(value):
                continue
        except Exception:
            pass
        try:
            return float(value)
        except Exception:
            continue
    return None


def _row_summary(row: pd.Series) -> dict:
    return {
        "rt_median": _coalesce_metric(row, "rt_median"),
        "prefire_rate": _coalesce_metric(row, "prefire_rate"),
        "thrusmoke_kill_rate": _coalesce_metric(row, "thrusmoke_kill_rate"),
        "headshot_rate": _coalesce_metric(row, "headshot_rate"),
        "long_range_fast_rt_rate_4": _coalesce_metric(row, "long_range_fast_rt_rate_4"),
    }


def _normalize_shares(items: list[dict]) -> list[dict]:
    total = sum(max(0.0, float(item.get("share", 0.0))) for item in items) or 1.0
    normalized = []
    running = 0.0
    for index, item in enumerate(items):
        share = max(0.0, float(item.get("share", 0.0))) / total
        if index == len(items) - 1:
            share = max(0.0, 1.0 - running)
        else:
            running += share
        normalized.append({**item, "share": round(share, 4)})
    return normalized


def _status_from_weight(weight: float, *, inverse: bool = False) -> str:
    value = 1.0 - weight if inverse else weight
    if value >= 0.72:
        return "high"
    if value >= 0.52:
        return "partial"
    if value >= 0.34:
        return "mixed"
    return "limited"


def _derive_archetype(mechanics: float, timing: float, occlusion: float, stability: float, sample_limit: float, context_fit: float) -> tuple[str, str]:
    if sample_limit >= 0.72 and stability < 0.5:
        return "Thin-evidence anomaly", "The standout pattern is interesting, but the sample is narrow enough that evidence stability remains limited."
    if occlusion >= max(mechanics, timing) and occlusion >= 0.24:
        return "Occlusion-heavy outlier", "The player separates most in compromised visibility states rather than through broad mechanical dominance."
    if timing >= max(mechanics, occlusion) and context_fit >= 0.58:
        return "Mechanical standout, context-consistent", "Most separation can be explained by strong match performance, with timing still worth a closer look."
    if timing >= max(mechanics, occlusion):
        return "Info-leaning anomaly", "The profile stands out through timing and first-contact behavior more than pure mechanical conversion."
    if mechanics >= 0.32 and stability >= 0.58 and context_fit >= 0.54:
        return "Stable standout", "The player is broadly strong across the match and much of the deviation remains context-consistent."
    if mechanics >= 0.3 and stability < 0.5:
        return "High-variance carry", "Mechanical output is elevated, but the signal narrows into a smaller set of rounds and fights."
    return "Mixed anomaly", "No single category fully explains the deviation, so the case should be read as a mixed profile rather than a one-note signal."


def _derive_interpretation(
    *,
    row: pd.Series | dict,
    rank: int | None = None,
    total_players: int | None = None,
    reasons: list[dict] | None = None,
    signals: dict | None = None,
) -> dict:
    reasons = reasons or []
    signals = signals or {}

    rt_median = _coalesce_metric(row, "rt_median")
    prefire = _clamp01(_coalesce_metric(row, "prefire_rate"))
    thrusmoke = _clamp01(_coalesce_metric(row, "thrusmoke_kill_rate"))
    headshot = _clamp01(_coalesce_metric(row, "headshot_rate"))
    long_fast = _clamp01(_coalesce_metric(row, "long_range_fast_rt_rate_4", "long_fast_rt_pct"))
    confidence = _clamp01(_coalesce_metric(row, "confidence", "confidence_score"))
    risk = _clamp01(_coalesce_metric(row, "risk", "score", "proba_calibrated", "proba_cheater_infer"))
    ci_low = _coalesce_metric(row, "ci_low", "risk_p05")
    ci_high = _coalesce_metric(row, "ci_high", "risk_p95")
    ci_width = max(0.0, (ci_high or risk) - (ci_low or risk)) if ci_low is not None and ci_high is not None else max(0.0, 0.2 - confidence * 0.12)

    timing_core = _clamp01((prefire * 0.52) + ((1.0 - min((rt_median or 12.0), 16.0) / 16.0) * 0.48))
    mechanics = _clamp01((headshot * 0.58) + (long_fast * 0.42))
    occlusion = _clamp01((thrusmoke * 0.8) + (long_fast * 0.2))
    decision = _clamp01((prefire * 0.3) + (confidence * 0.3) + ((1.0 - thrusmoke) * 0.18) + ((1.0 - min((rt_median or 12.0), 18.0) / 18.0) * 0.22))
    sample_limit = _clamp01(max(0.0, 0.92 - confidence * 0.72 + ci_width * 0.8))
    stability = _clamp01(confidence * 0.62 + (1.0 - sample_limit) * 0.38)
    behavior_deviation = _clamp01(max(risk, (timing_core * 0.34) + (mechanics * 0.22) + (occlusion * 0.22) + (decision * 0.12) + (stability * 0.1)))

    if rank is not None and total_players and total_players > 1:
        lobby_topness = _clamp01(1.0 - ((rank - 1) / (total_players - 1)))
    else:
        lobby_topness = behavior_deviation

    skill_gap_weight = _clamp01((mechanics * 0.58) + (headshot * 0.22) + (confidence * 0.12) - (occlusion * 0.08))
    weak_pool_weight = _clamp01((lobby_topness * 0.18) + (sample_limit * 0.42) + ((1.0 - stability) * 0.22) + (mechanics * 0.18))
    map_weight = _clamp01(0.18 + mechanics * 0.2 + confidence * 0.12 - timing_core * 0.1)
    side_weight = _clamp01(0.24 + sample_limit * 0.24 + occlusion * 0.12)
    weapon_weight = _clamp01(0.26 + mechanics * 0.18 + long_fast * 0.18 - stability * 0.08)
    engagement_weight = _clamp01(0.22 + timing_core * 0.24 + prefire * 0.16)

    explanation_pressure = (skill_gap_weight * 0.24) + (weak_pool_weight * 0.18) + (map_weight * 0.12) + (side_weight * 0.12) + (weapon_weight * 0.12) + (engagement_weight * 0.1) + (sample_limit * 0.12)
    context_fit = _clamp01(1.0 - explanation_pressure + mechanics * 0.08 + stability * 0.1)
    review_priority = _clamp01((behavior_deviation * 0.4) + ((1.0 - context_fit) * 0.2) + (stability * 0.18) + (occlusion * 0.12) + (timing_core * 0.1))

    round_spread = _clamp01(stability * 0.62 + (1.0 - sample_limit) * 0.18 + timing_core * 0.2)
    half_spread = _clamp01(stability * 0.72 + confidence * 0.1)
    weapon_spread = _clamp01((1.0 - weapon_weight) * 0.54 + mechanics * 0.18 + confidence * 0.14)
    visibility_spread = _clamp01(occlusion * 0.58 + timing_core * 0.18 + stability * 0.14)
    engagement_spread = _clamp01((1.0 - engagement_weight) * 0.36 + timing_core * 0.32 + decision * 0.18 + confidence * 0.08)

    components = _normalize_shares([
        {"key": "mechanics", "label": "Mechanics", "share": mechanics + 0.02, "summary": "Mechanical conversion contributes to the standout profile." if mechanics >= 0.28 else "Mechanical output is not the main story here."},
        {"key": "information_timing", "label": "Information / timing", "share": timing_core + 0.02, "summary": "First-contact timing and visibility-to-shot behavior shape the deviation." if timing_core >= 0.28 else "Timing is present but not dominant."},
        {"key": "occlusion", "label": "Occlusion", "share": occlusion + 0.02, "summary": "Low-visibility engagements contribute materially." if occlusion >= 0.2 else "Occlusion is only a secondary contributor."},
        {"key": "decision_discipline", "label": "Decision discipline", "share": decision * 0.65 + 0.02, "summary": "The shape depends partly on selective engagement choices and setup quality."},
        {"key": "concentration", "label": "Stability / concentration", "share": (1.0 - stability) * 0.56 + stability * 0.16 + 0.02, "summary": "This captures whether the signal is broad or concentrated."},
    ])

    archetype_label, archetype_summary = _derive_archetype(mechanics, timing_core, occlusion, stability, sample_limit, context_fit)
    dominant_component = max(components, key=lambda item: float(item.get("share", 0.0)))
    behavior_headline = {
        "information_timing": "Stands out mostly through timing and sequencing, not pure mechanics.",
        "occlusion": "Stands out mostly in low-visibility engagements and occlusion-heavy moments.",
        "mechanics": "Shows strong mechanical separation, though context still matters.",
        "concentration": "The anomaly is narrow and concentrated rather than broad across the match.",
    }.get(dominant_component["key"], "This is a mixed standout profile rather than a one-metric case.")
    behavior_summary = archetype_summary

    context_items = [
        {"key": "skill_gap", "label": "Skill gap explanation", "status": _status_from_weight(skill_gap_weight), "weight": round(skill_gap_weight, 4), "summary": "Mechanical edge explains part of the separation." if skill_gap_weight >= 0.5 else "Mechanical superiority does not fully explain the pattern."},
        {"key": "weak_pool", "label": "Weak opponent pool", "status": _status_from_weight(weak_pool_weight), "weight": round(weak_pool_weight, 4), "summary": "A softer lobby may inflate match-relative separation." if weak_pool_weight >= 0.45 else "Lobby strength alone is not enough to explain the shape."},
        {"key": "sample_size", "label": "Sample size limitation", "status": _status_from_weight(sample_limit), "weight": round(sample_limit, 4), "summary": "This remains a single-match sample with finite event volume."},
        {"key": "side_mix", "label": "Side imbalance", "status": _status_from_weight(side_weight), "weight": round(side_weight, 4), "summary": "The standout pattern may be helped by side-specific opportunity."},
        {"key": "weapon_mix", "label": "Weapon mix", "status": _status_from_weight(weapon_weight), "weight": round(weapon_weight, 4), "summary": "Weapon selection likely contributes some of the separation."},
        {"key": "map_context", "label": "Map familiarity", "status": _status_from_weight(map_weight), "weight": round(map_weight, 4), "summary": "Map comfort is a plausible but limited explanation."},
    ]

    remaining_signal = "yes" if context_fit <= 0.42 else "mixed" if context_fit <= 0.62 else "uncertain"
    context_summary = (
        "Several ordinary explanations partially account for the standout profile, but the remaining signal is still worth review."
        if remaining_signal == "yes"
        else "Some of the deviation survives context adjustment, but the case remains mixed rather than decisive."
        if remaining_signal == "mixed"
        else "Contextual explanations account for much of the match-relative separation in this sample."
    )

    review_title = (
        "Compare POV in low-visibility engagements"
        if occlusion >= max(mechanics, timing_core)
        else "Review timing around first-contact fights"
        if timing_core >= mechanics
        else "Compare opponent POV in standout rounds"
    )
    review_summary = (
        "Best follow-up is to isolate the situations that drive this profile rather than treating the aggregate score as the conclusion."
    )
    review_comparisons = [
        review_title,
        "Cross-check standout rounds against opponent POV",
        "Look for repeatable patterns rather than isolated highlights",
    ]

    limitations = [
        {"label": "Match-only sample", "severity": "high", "summary": "This interpretation is limited to one match and should not be treated as a longitudinal claim."},
        {"label": "Signal concentration", "severity": "medium" if stability < 0.58 else "low", "summary": "The profile is concentrated rather than evenly persistent across every round." if stability < 0.58 else "The signal is broader than a single burst, but still match-bounded."},
        {"label": "Context calibration", "severity": "medium", "summary": "Lobby strength, side distribution, and weapon mix can distort match-relative deviation."},
    ]
    if sample_limit >= 0.6:
        limitations.append({"label": "Low event volume", "severity": "high", "summary": "Support is limited by event density and uncertainty width."})

    high_reason_count = sum(1 for reason in reasons if str(reason.get("severity", "")).lower() == "high")
    if high_reason_count >= 2 and review_priority < 0.65:
        review_priority = _clamp01(review_priority + 0.08)

    return {
        "archetype": {"label": archetype_label, "summary": archetype_summary},
        "behavior_profile": {"headline": behavior_headline, "summary": behavior_summary},
        "behavioral_deviation": round(behavior_deviation, 4),
        "context_fit": round(context_fit, 4),
        "signal_stability": round(stability, 4),
        "review_priority": round(review_priority, 4),
        "support_level": round(confidence, 4),
        "signal_components": components,
        "context_adjustment": {
            "summary": context_summary,
            "remaining_signal": remaining_signal,
            "normal_explanations": context_items,
        },
        "durability": {
            "summary": "The signal is persistent enough to inspect, but not broad enough to treat as self-explanatory." if stability >= 0.52 else "The standout pattern is narrow and should be read as concentrated rather than durable.",
            "metrics": [
                {"key": "rounds", "label": "Across rounds", "value": round(round_spread, 4), "summary": "Indicates whether the pattern holds beyond a few standout rounds."},
                {"key": "halves", "label": "Across halves", "value": round(half_spread, 4), "summary": "Checks whether the shape survives side and half changes."},
                {"key": "weapons", "label": "Across weapons", "value": round(weapon_spread, 4), "summary": "Higher values mean the signal is less weapon-specific."},
                {"key": "visibility", "label": "Across visibility states", "value": round(visibility_spread, 4), "summary": "Higher values mean the pattern is most visible in compromised sightlines."},
                {"key": "engagements", "label": "Across engagement types", "value": round(engagement_spread, 4), "summary": "Higher values mean the profile survives beyond one engagement pattern."},
            ],
        },
        "review_lens": {
            "title": review_title,
            "summary": review_summary,
            "comparisons": review_comparisons,
        },
        "limitations": limitations,
        "model_notes": [
            "TODO: context fit, durability, and review priority are currently heuristic-derived from available per-match features and explain outputs.",
            "TODO: replace these placeholders with round-aware, side-aware, and opponent-aware modeling when richer DS features are available.",
        ],
    }


def _parse_top_reasons(val) -> list[dict]:
    if isinstance(val, list):
        return val
    if isinstance(val, str) and val.strip():
        try:
            parsed = json.loads(val)
            if isinstance(parsed, list):
                return parsed
        except Exception:
            return []
    return []


def _enrich_report_payload(report: dict, *, fallback_row: pd.Series | dict | None = None, rank: int | None = None, total_players: int | None = None) -> dict:
    enriched = dict(report or {})
    player = enriched.get("player") or {}
    risk = enriched.get("risk") or {}
    confidence = enriched.get("confidence") or {}
    uncertainty_ci = enriched.get("uncertainty_ci") or {}

    summary_seed = dict(fallback_row) if isinstance(fallback_row, dict) else {}
    if not summary_seed:
        signal_values = (enriched.get("signals") or {}).get("raw_values") or {}
        summary_seed = dict(signal_values)

    enriched["interpretation"] = interpretation_from_summary(
        summary_seed,
        risk=risk.get("score"),
        confidence=confidence.get("score"),
        ci_low=uncertainty_ci.get("risk_p05"),
        ci_high=uncertainty_ci.get("risk_p95"),
        rank=rank,
        total_players=total_players,
    )
    enriched.setdefault("player", player)
    return enriched


@api.get("/demo/{demo_id}/players")
def demo_players(demo_id: str, debug: int = Query(default=0)) -> dict:
    safe_demo_id = _sanitize_segment(demo_id, "demo_id")
    if not INFER_CSV.exists():
        raise HTTPException(status_code=404, detail="Inference results are not available")
    df = pd.read_csv(INFER_CSV)
    data = df[df["demo_id"].astype(str) == safe_demo_id].copy()
    if data.empty:
        return {"demo_id": safe_demo_id, "players": []}
    sort_col = "risk" if "risk" in data.columns else "proba_cheater_infer"
    data = data.sort_values(sort_col, ascending=False).reset_index(drop=True)

    interpretation_map: dict[str, dict] = {}
    summary_map: dict[str, dict] = {}
    try:
        eng, enc = load_demo_frames(safe_demo_id)
        interpretation_map = build_demo_interpretations(data, eng, enc)
        summary_df = build_demo_player_summary(eng, enc)
        if not summary_df.empty:
            summary_map = {str(row["attacker_steamid"]): row.to_dict() for _, row in summary_df.iterrows()}
    except FileNotFoundError:
        interpretation_map = {}
        summary_map = {}

    players = []
    total_players = int(len(data))
    for rank_idx, (_, row) in enumerate(data.iterrows(), start=1):
        risk = float(row.get("risk", row.get("proba_calibrated", row.get("proba_cheater_infer", 0.0))))
        reasons = _parse_top_reasons(row.get("top_reasons"))
        steamid = str(row.get("attacker_steamid", "")).strip()
        fallback_summary = summary_map.get(steamid, _row_summary(row))
        interpretation = interpretation_map.get(steamid) or interpretation_from_summary(
            fallback_summary,
            risk=risk,
            confidence=float(row.get("confidence", 0.0)),
            ci_low=(None if pd.isna(row.get("ci_low")) else float(row.get("ci_low"))),
            ci_high=(None if pd.isna(row.get("ci_high")) else float(row.get("ci_high"))),
            rank=rank_idx,
            total_players=total_players,
        )
        players.append(
            {
                "steamid": steamid,
                "attacker_name": str(row.get("attacker_name", "")),
                "proba_cheater_infer": float(row.get("proba_cheater_infer", 0.0)),
                "risk": risk,
                "confidence": float(row.get("confidence", 0.0)),
                "ci_low": (None if pd.isna(row.get("ci_low")) else float(row.get("ci_low"))),
                "ci_high": (None if pd.isna(row.get("ci_high")) else float(row.get("ci_high"))),
                "risk_band": str(row.get("risk_band", "")),
                "top_reasons": reasons,
                "features_summary": _row_summary(row),
                "interpretation": interpretation,
            }
        )
    def _player_sort_score(item: dict) -> float:
        interpretation = item.get("interpretation") if isinstance(item.get("interpretation"), dict) else {}
        risk_val = float(item.get("risk") or item.get("proba_cheater_infer") or 0.0)
        review_val = float(interpretation.get("review_priority") or risk_val)
        return (risk_val * 0.72) + (review_val * 0.28)

    players.sort(key=_player_sort_score, reverse=True)
    total_players = int(len(players))
    for rank_idx, player in enumerate(players, start=1):
        interpretation = player.get("interpretation")
        if not isinstance(interpretation, dict):
            continue
        match_profile = interpretation.get("match_profile")
        if not isinstance(match_profile, dict):
            continue
        stats = match_profile.get("stats")
        if not isinstance(stats, list):
            continue
        for stat in stats:
            if not isinstance(stat, dict):
                continue
            if stat.get("key") == "rank":
                stat["display_value"] = f"#{rank_idx}/{total_players}"
                stat["value"] = (float(rank_idx) / float(total_players)) if total_players else None
            elif stat.get("key") == "lobby_percentile":
                percentile = max(0.0, min(1.0, 1.0 - ((rank_idx - 1) / max(1, total_players - 1)))) if total_players > 1 else 1.0
                stat["display_value"] = f"{percentile * 100:.1f}%"
                stat["value"] = round(percentile, 4)
        match_profile["summary"] = (
            f"Ranked #{rank_idx} of {total_players} in this lobby. The standout shape comes from actual per-match event structure rather than a generic leaderboard score."
            if total_players
            else match_profile.get("summary")
        )
    response: dict[str, object] = {"demo_id": safe_demo_id, "players": players}
    if int(debug) == 1 and ENABLE_DIAGNOSTICS:
        response["debug"] = {"enabled": True, "trace": _load_debug_trace(safe_demo_id)}
    return response


@api.get("/demo/{demo_id}/player/{steamid}/score-trace")
def player_score_trace(demo_id: str, steamid: str) -> dict:
    safe_demo_id = _sanitize_segment(demo_id, "demo_id")
    safe_steamid = _sanitize_segment(steamid, "steamid")
    trace = _load_debug_trace(safe_demo_id)
    players = trace.get("players", []) if isinstance(trace, dict) else []
    for player in players:
        if str(player.get("steamid", "")).strip() == safe_steamid:
            return {"demo_id": safe_demo_id, "steamid": safe_steamid, "trace": player}
    raise HTTPException(status_code=404, detail="No score trace found for that player")


@api.post("/demo/{demo_id}/player/{steamid}/explain")
def explain_player(demo_id: str, steamid: str) -> dict:
    safe_demo_id = _sanitize_segment(demo_id, "demo_id")
    safe_steamid = _sanitize_segment(steamid, "steamid")
    if DEMO_MODE:
        raise HTTPException(status_code=403, detail="Public demo mode does not generate explainability reports")

    log_dir = REPORTS_DIR / safe_demo_id / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"explain_{safe_steamid}.log"
    cmd = [
        *([PIPELINE_EXE, "explain"] if PIPELINE_EXE else [str(PYTHON_EXE), str(SCRIPTS_DIR / "explain_demo.py")]),
        "--demo",
        safe_demo_id,
        "--steamid",
        safe_steamid,
        "--mode",
        "infer",
    ]
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=EXPLAIN_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Explain job timed out")

    log_path.write_text((proc.stdout or "") + "\n" + (proc.stderr or ""), encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        raise HTTPException(status_code=500, detail="Explain job failed")

    out_dir = _safe_report_dir(safe_demo_id, safe_steamid)
    return {
        "demo_id": safe_demo_id,
        "steamid": safe_steamid,
        "evidence_files": [path.name for path in sorted(out_dir.glob("evidence_*.csv")) if SAFE_FILENAME_RE.fullmatch(path.name)],
    }


@api.get("/explain")
def api_explain(
    demo_id: str = Query(...),
    steamid: str = Query(...),
    mode: str = Query(default="infer"),
    ci: int = Query(default=0),
    n_boot: int = Query(default=100),
) -> dict:
    safe_demo_id = _sanitize_segment(demo_id, "demo_id")
    safe_steamid = _sanitize_segment(steamid, "steamid")
    normalized_mode = str(mode).strip().lower()
    if normalized_mode not in {"oof", "insample", "infer"}:
        raise HTTPException(status_code=400, detail="mode must be one of: oof, insample, infer")

    try:
        if str(PROJECT_ROOT / "main") not in sys.path:
            sys.path.insert(0, str(PROJECT_ROOT / "main"))
        from src.utils.explain_demo import default_config, explain_demo

        cfg = default_config(mode=normalized_mode)
        explain_demo(
            cfg,
            demo_id=safe_demo_id,
            steamid=safe_steamid,
            with_ci=bool(int(ci)),
            n_boot=int(max(20, n_boot)),
        )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Explain failed")

    out_dir = _safe_report_dir(safe_demo_id, safe_steamid)
    report_path = out_dir / "report.json"
    if not report_path.exists():
        raise HTTPException(status_code=404, detail="Report not found")
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to parse report")

    fallback_row = None
    rank = None
    total_players = None
    if INFER_CSV.exists():
        try:
            df = pd.read_csv(INFER_CSV)
            data = df[df["demo_id"].astype(str) == safe_demo_id].copy()
            if not data.empty:
                sort_col = "risk" if "risk" in data.columns else "proba_cheater_infer"
                data = data.sort_values(sort_col, ascending=False).reset_index(drop=True)
                total_players = int(len(data))
                match_idx = data.index[data["attacker_steamid"].astype(str) == safe_steamid]
                if len(match_idx):
                    rank = int(match_idx[0]) + 1
                    fallback_row = data.iloc[int(match_idx[0])].to_dict()
        except Exception:
            fallback_row = None

    return _sanitize_trace(_enrich_report_payload(report, fallback_row=fallback_row, rank=rank, total_players=total_players))


@api.get("/demo/{demo_id}/player/{steamid}/report/files")
def player_report_files(demo_id: str, steamid: str) -> dict:
    out_dir = _safe_report_dir(demo_id, steamid)
    if not out_dir.exists():
        raise HTTPException(status_code=404, detail="Report folder not found")
    return {
        "demo_id": _sanitize_segment(demo_id, "demo_id"),
        "steamid": _sanitize_segment(steamid, "steamid"),
        "report_exists": (out_dir / "report.json").exists(),
        "reasons_exists": (out_dir / "reasons.json").exists(),
        "top_row_exists": (out_dir / "top_player_row.json").exists(),
        "evidence_files": [path.name for path in sorted(out_dir.glob("evidence_*.csv")) if SAFE_FILENAME_RE.fullmatch(path.name)],
    }


@api.get("/demo/{demo_id}/player/{steamid}/report/reasons")
def player_report_reasons(demo_id: str, steamid: str) -> dict:
    safe_demo_id = _sanitize_segment(demo_id, "demo_id")
    safe_steamid = _sanitize_segment(steamid, "steamid")
    out_dir = _safe_report_dir(safe_demo_id, safe_steamid)
    reasons_path = out_dir / "reasons.json"
    if not reasons_path.exists():
        raise HTTPException(status_code=404, detail="Reasons file not found")
    try:
        reasons = json.loads(reasons_path.read_text(encoding="utf-8"))
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to parse reasons")
    if not isinstance(reasons, list):
        reasons = []
    return {"demo_id": safe_demo_id, "steamid": safe_steamid, "reasons": _sanitize_trace(reasons)}


@api.get("/demo/{demo_id}/player/{steamid}/report/evidence/{filename}")
def player_report_evidence(demo_id: str, steamid: str, filename: str, limit: int = 500) -> dict:
    safe_demo_id = _sanitize_segment(demo_id, "demo_id")
    safe_steamid = _sanitize_segment(steamid, "steamid")
    path = _safe_evidence_path(safe_demo_id, safe_steamid, filename)
    try:
        df = pd.read_csv(path)
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to parse evidence")

    safe_limit = max(1, min(int(limit), 2000))
    if len(df) > safe_limit:
        df = df.head(safe_limit)
    columns, rows = _sanitize_dataframe(df)
    return {
        "demo_id": safe_demo_id,
        "steamid": safe_steamid,
        "filename": Path(filename).name,
        "columns": columns,
        "rows": rows,
        "row_count": len(df),
    }


@api.get("/demo/{demo_id}/player/{steamid}/report")
def player_report(demo_id: str, steamid: str) -> dict:
    safe_demo_id = _sanitize_segment(demo_id, "demo_id")
    safe_steamid = _sanitize_segment(steamid, "steamid")
    out_dir = _safe_report_dir(safe_demo_id, safe_steamid)
    if not out_dir.exists():
        raise HTTPException(status_code=404, detail="Report folder not found")
    reasons_path = out_dir / "reasons.json"
    reasons = []
    if reasons_path.exists():
        try:
            reasons = json.loads(reasons_path.read_text(encoding="utf-8"))
        except Exception:
            raise HTTPException(status_code=500, detail="Failed to parse reasons")

    evidence = []
    for path in sorted(out_dir.glob("evidence_*.csv")):
        if not SAFE_FILENAME_RE.fullmatch(path.name):
            continue
        df = pd.read_csv(path).head(50)
        columns, rows = _sanitize_dataframe(df)
        evidence.append({"filename": path.name, "columns": columns, "row_count": int(len(df)), "preview": rows})
    return {"demo_id": safe_demo_id, "steamid": safe_steamid, "reasons": _sanitize_trace(reasons), "evidence": evidence}

app.include_router(api)

"""Owned website jobs, direct streamed uploads, and the canonical inference boundary.

SQLite and private disk storage deliberately keep this a single-host worker. The
exclusive process lock and serial executor protect the research CSV's read/rewrite.
"""
from __future__ import annotations

import asyncio
import datetime as dt
import hashlib
import json
import logging
import math
import os
import re
import secrets
import shutil
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

import pandas as pd
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator
from starlette.concurrency import run_in_threadpool

from .pipeline_runtime import PipelineFailure, STAGE_LABELS, inference_command, run_process

router = APIRouter(prefix="/api/analysis")
logger = logging.getLogger("nullcs.analysis")
JOB_RE = re.compile(r"^TEST_[0-9]{14}_[0-9a-f]{32}$")
SID_RE = re.compile(r"^[0-9]{1,20}$")
EVIDENCE_RE = re.compile(r"^evidence_[A-Za-z0-9_-]{1,80}\.csv$")


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="milliseconds")


def clean(value):
    """Public serialization: finite numbers, no internal fields or filesystem paths."""
    if isinstance(value, dict):
        return {str(k): clean(v) for k, v in value.items()
                if not any(x in str(k).lower() for x in ("path", "feature_row", "feature_vector_hash", "uploader_ip", "pid", "log_"))}
    if isinstance(value, (list, tuple)):
        return [clean(v) for v in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, str):
        return re.sub(r"(?i)(?:[a-z]:[\\/]|/(?:app|tmp|home|opt|var|srv)/)[^\s\"<>]*", "[private path]", value)[:4000]
    return value


def write_json(path: Path, payload: dict) -> None:
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(clean(payload), ensure_ascii=False, allow_nan=False), encoding="utf-8")
    temporary.replace(path)


class UploadMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    filename: str = Field(min_length=5, max_length=128)
    size: StrictInt = Field(ge=16)

    @field_validator("filename")
    @classmethod
    def filename_is_safe(cls, value):
        if any(c in value for c in ('/', '\\', ':')) or any(ord(c) < 32 for c in value) or not value.lower().endswith('.dem'):
            raise ValueError("Expected a .dem basename")
        return value


class AnalysisService:
    def __init__(self, settings):
        self.settings = settings
        self.root = Path(settings.WEB_STATE_DIR)
        self.db_path = self.root / "analysis.sqlite3"
        self.stopping = threading.Event()
        self.thread = None
        self.lock_file = None

    @contextmanager
    def db(self):
        db = sqlite3.connect(self.db_path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            with db:
                yield db
        finally:
            db.close()

    def start(self):
        if not self.settings.NULLCS_API_KEY or len(self.settings.NULLCS_API_KEY) < 32:
            raise RuntimeError("Website worker requires NULLCS_API_KEY with at least 32 characters")
        if self.settings.DEMO_MODE:
            raise RuntimeError("Website analysis requires NULLCS_DEMO_MODE=0")
        if self.settings.PIPELINE_EXE:
            raise RuntimeError("Website analysis requires the Python pipeline, not the generated desktop executable")
        if Path(self.settings.PROCESSED_DIR).resolve() == (Path(self.settings.PROJECT_ROOT) / 'main/data/processed').resolve():
            raise RuntimeError("Website analysis requires a dedicated CLARITY_PROCESSED_DIR; do not write into research outputs")
        if not 16 <= self.settings.WEB_MAX_UPLOAD_BYTES <= 10 * 1024 ** 3:
            raise RuntimeError("Invalid website upload limit")
        for p in (self.root, self.settings.UPLOAD_DIR, self.settings.PROCESSED_DIR):
            Path(p).mkdir(parents=True, exist_ok=True)
        # Lock the processed root, not a process-local thread lock. Never share this
        # research output directory with a separately launched inference CLI.
        self.lock_file = (Path(self.settings.PROCESSED_DIR) / ".web-worker.lock").open("a+b")
        self.lock_file.write(b"0")
        self.lock_file.flush()
        self.lock_file.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self.lock_file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.lock_file.close()
            raise RuntimeError("Only one website worker may use a processed directory")
        with self.db() as db:
            db.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY, owner TEXT NOT NULL, filename TEXT NOT NULL,
                    size INTEGER NOT NULL, ticket_hash TEXT NOT NULL, expires REAL NOT NULL,
                    state TEXT NOT NULL, stage TEXT NOT NULL, created TEXT NOT NULL,
                    updated TEXT NOT NULL, started TEXT, finished TEXT,
                    error_code TEXT, error_message TEXT, runtime REAL, upload_sha256 TEXT
                );
                CREATE TABLE IF NOT EXISTS events (job TEXT, stage TEXT, at TEXT);
                CREATE TABLE IF NOT EXISTS explanations (
                    job TEXT REFERENCES jobs(id), steamid TEXT, state TEXT NOT NULL,
                    error_message TEXT, updated TEXT NOT NULL, PRIMARY KEY(job, steamid)
                );
            """)
            interrupted = db.execute("SELECT id,state FROM jobs WHERE state IN ('running','uploading')").fetchall()
            for row in interrupted:
                db.execute("UPDATE jobs SET state='failed',stage='failed',error_code='worker_restarted',error_message=?,updated=?,finished=? WHERE id=?",
                           ("The worker restarted before this analysis completed. Please upload the demo again.", now(), now(), row['id']))
                db.execute("INSERT INTO events VALUES (?,?,?)", (row['id'], 'failed', now()))
                if row['state'] == 'uploading':
                    self.cleanup_upload(row['id'])
            db.execute("UPDATE explanations SET state='failed',error_message='Explanation interrupted by worker restart',updated=? WHERE state='running'", (now(),))
        self.thread = threading.Thread(target=self.work, name="nullcs-analysis", daemon=True)
        self.thread.start()

    def stop(self):
        self.stopping.set()
        if self.thread:
            self.thread.join(timeout=15)
        if self.lock_file and (not self.thread or not self.thread.is_alive()):
            self.lock_file.close()

    def source(self, job):
        return Path(self.settings.UPLOAD_DIR) / job / f"{job}.dem"

    def partial(self, job):
        return self.source(job).with_suffix(".partial")

    def cleanup_upload(self, job):
        for path in (self.partial(job), self.source(job)):
            try:
                path.unlink(missing_ok=True)
            except OSError:
                # Persist failure even when the filesystem prevents cleanup.
                logger.exception("Could not remove failed upload for %s", job)

    def report_dir(self, job):
        return Path(self.settings.REPORTS_DIR) / job

    def owned(self, job, owner):
        if not JOB_RE.fullmatch(job):
            raise HTTPException(404, "Analysis not found")
        with self.db() as db:
            row = db.execute("SELECT * FROM jobs WHERE id=? AND owner=?", (job, owner)).fetchone()
        if row is None:
            raise HTTPException(404, "Analysis not found")
        return dict(row)

    def update(self, job, **fields):
        fields['updated'] = now()
        with self.db() as db:
            db.execute(f"UPDATE jobs SET {','.join(k+'=?' for k in fields)} WHERE id=?", (*fields.values(), job))
            if 'stage' in fields:
                db.execute("INSERT INTO events VALUES (?,?,?)", (job, fields['stage'], fields['updated']))

    def create(self, owner, metadata):
        if metadata.size > self.settings.WEB_MAX_UPLOAD_BYTES:
            raise HTTPException(413, "Demo exceeds the configured upload size limit")
        ticket = secrets.token_urlsafe(32)
        job = "TEST_" + dt.datetime.now(dt.timezone.utc).strftime('%Y%m%d%H%M%S') + "_" + uuid.uuid4().hex
        timestamp = now()
        expires = time.time() + self.settings.WEB_UPLOAD_TIMEOUT_SECONDS
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            pending = db.execute("SELECT owner,size FROM jobs WHERE state IN ('upload_pending','uploading','queued','running')").fetchall()
            if len(pending) >= self.settings.WEB_MAX_PENDING_JOBS or sum(r['owner'] == owner for r in pending) >= 2:
                raise HTTPException(429, "Analysis capacity is currently full. Try again after an active job finishes.")
            reserved = sum(r['size'] for r in pending)
            if shutil.disk_usage(self.settings.UPLOAD_DIR).free < reserved + metadata.size + self.settings.WEB_MIN_FREE_BYTES:
                raise HTTPException(503, "Insufficient worker storage for this upload")
            db.execute("INSERT INTO jobs (id,owner,filename,size,ticket_hash,expires,state,stage,created,updated) VALUES (?,?,?,?,?,?,'upload_pending','upload_pending',?,?)",
                       (job, owner, metadata.filename, metadata.size, hashlib.sha256(ticket.encode()).hexdigest(), expires, timestamp, timestamp))
            db.execute("INSERT INTO events VALUES (?,?,?)", (job, "upload_pending", timestamp))
        return {"job_id": job, "upload_path": f"/api/analysis/{job}/upload", "upload_token": ticket,
                "expires_at": dt.datetime.fromtimestamp(expires, dt.timezone.utc).isoformat(),
                "max_upload_bytes": self.settings.WEB_MAX_UPLOAD_BYTES}

    def claim_upload(self, job, ticket):
        if not JOB_RE.fullmatch(job) or len(ticket) > 128:
            raise HTTPException(404, "Upload not available")
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM jobs WHERE id=?", (job,)).fetchone()
            if row is None or not secrets.compare_digest(row['ticket_hash'], hashlib.sha256(ticket.encode()).hexdigest()):
                raise HTTPException(404, "Upload not available")
            if row['state'] != 'upload_pending' or row['expires'] < time.time():
                raise HTTPException(409, "Upload ticket has expired or has already been used")
            db.execute("UPDATE jobs SET state='uploading',stage='uploading',updated=? WHERE id=?", (now(), job))
            db.execute("INSERT INTO events VALUES (?,?,?)", (job, "uploading", now()))
        return dict(row)

    def status(self, job, owner):
        row = self.owned(job, owner)
        with self.db() as db:
            events = [dict(r) for r in db.execute("SELECT stage,at FROM events WHERE job=? ORDER BY rowid", (job,))]
        return {"schema_version": "nullcs.analysis.v1", "job_id": job, "state": row['state'],
                "stage": row['stage'], "stage_label": STAGE_LABELS[row['stage']],
                "filename": row['filename'], "created_at": row['created'], "started_at": row['started'],
                "finished_at": row['finished'], "runtime_seconds": row['runtime'], "events": events,
                "error": {"code": row['error_code'], "message": row['error_message']} if row['error_code'] else None}

    def work(self):
        while not self.stopping.is_set():
            try:
                with self.db() as db:
                    expired = db.execute("SELECT id FROM jobs WHERE state='upload_pending' AND expires<?", (time.time(),)).fetchall()
                    for row in expired:
                        db.execute("INSERT INTO events VALUES (?,?,?)", (row['id'], 'failed', now()))
                    db.execute("UPDATE jobs SET state='failed',stage='failed',error_code='upload_expired',error_message='Upload expired. Please select the demo again.',updated=?,finished=? WHERE state='upload_pending' AND expires<?", (now(), now(), time.time()))
                    job = db.execute("SELECT * FROM jobs WHERE state='queued' ORDER BY created LIMIT 1").fetchone()
                    explanation = db.execute("SELECT * FROM explanations WHERE state='queued' ORDER BY updated LIMIT 1").fetchone()
                    if job and explanation and explanation['updated'] < job['created']:
                        job = None
                if job:
                    self.execute(dict(job))
                elif explanation:
                    self.execute_explanation(dict(explanation))
                else:
                    self.stopping.wait(.25)
            except Exception:
                logger.exception("Analysis scheduler failed")
                self.stopping.wait(1)

    def execute(self, row):
        job = row['id']
        self.update(job, state="running", stage="preparing", started=now())
        try:
            cmd, env = inference_command(self.settings, job, self.source(job))
            runtime = run_process(cmd, cwd=self.settings.PROJECT_ROOT, env=env,
                                  log=self.report_dir(job) / "logs" / "pipeline.log",
                                  timeout=self.settings.JOB_TIMEOUT_SECONDS,
                                  on_stage=lambda stage: self.update(job, stage=stage), stopping=self.stopping)
            payload = self.build_result(job, row)
            write_json(self.report_dir(job) / "web_result.json", payload)
            self.update(job, state="results_ready", stage="results_ready", finished=now(), runtime=runtime)
        except PipelineFailure as exc:
            logger.exception("Pipeline failed for %s", job)
            self.update(job, state="failed", stage="failed", finished=now(), error_code=exc.code, error_message=str(exc))
        except Exception:
            logger.exception("Result publication failed for %s", job)
            self.update(job, state="failed", stage="failed", finished=now(), error_code="result_failed",
                        error_message="The worker could not publish a complete analysis result. Detailed diagnostics are available to the service operator.")

    def build_result(self, job, row):
        from .main import players_from_frame
        root = self.report_dir(job)
        manifest = json.loads((root / "infer_manifest.json").read_text(encoding='utf8'))
        trace = json.loads((root / "debug_score_trace.json").read_text(encoding='utf8'))
        data = pd.read_csv(root / "ranked_players_infer.csv", dtype={"attacker_steamid": str})
        if data.empty or set(data['demo_id'].astype(str)) != {job} or manifest.get('demo_id') != job:
            raise ValueError("Incomplete or mismatched inference artifacts")
        players = players_from_frame(job, data, review_order=False)
        scores = data.set_index('attacker_steamid')
        for rank, player in enumerate(players, start=1):
            sid = player['steamid']
            if not SID_RE.fullmatch(sid):
                raise ValueError("Invalid player identifier in inference output")
            record = scores.loc[sid]
            player.update(rank=rank, model_score=float(record['proba_cheater_infer']),
                          calibrated_probability=None if pd.isna(record.get('proba_calibrated')) else float(record['proba_calibrated']),
                          explanation={"state": "unavailable", "error": None})
        warnings = []
        if not trace.get('calibration_used'):
            warnings.append({"code": "calibration_unavailable", "message": "The selected model has no calibration artifact. Scores are uncalibrated; existing low-evidence adjustments still apply."})
        log = (root / "logs/pipeline.log").read_text(encoding='utf8', errors='replace')
        if "InconsistentVersionWarning" in log:
            warnings.append({"code": "calibrator_version", "message": "The saved calibrator was created with a different scikit-learn version. The existing artifact was used without substitution."})
        provenance = manifest.get('parser_provenance') or {}
        if provenance.get('demoparser2_version') == '0.41.4':
            warnings.append({"code": "parser_limitation", "message": "Parser 0.41.4 has a known upstream issue with stale user-command values in some newer demos. A passing schema check cannot rule this out. Treat results as research review signals."})
        return {"schema_version": "nullcs.analysis.v1", "job_id": job, "ranking": "pipeline_risk_descending",
                "demo": {"filename": row['filename'], "size_bytes": row['size'], "map_name": str(data['map_name'].iloc[0]),
                         "parser_provenance": {k: provenance.get(k) for k in ('patch_version','demo_version_name','demo_version_guid','map_name','demoparser2_version')}},
                "model": {"artifact_name": Path(str(trace['model_artifact_path'])).name,
                          "sha256": trace.get('model_sha256'), "feature_list_sha256": trace.get('feature_list_sha256'),
                          "calibration_used": bool(trace.get('calibration_used'))},
                "players": players, "warnings": warnings}

    def results(self, job, owner):
        row = self.owned(job, owner)
        if row['state'] != 'results_ready':
            raise HTTPException(409, "Analysis results are not ready")
        try:
            result = json.loads((self.report_dir(job) / "web_result.json").read_text(encoding='utf8'))
        except (OSError, ValueError):
            raise HTTPException(503, "Stored analysis results are unavailable")
        with self.db() as db:
            states = {r['steamid']: dict(r) for r in db.execute("SELECT * FROM explanations WHERE job=?", (job,))}
        for player in result['players']:
            e = states.get(player['steamid'])
            player['explanation'] = {"state": e['state'] if e else 'unavailable', "error": e['error_message'] if e else None}
        result['status'] = self.status(job, owner)
        return result

    def player(self, job, owner, sid):
        result = self.results(job, owner)
        if not SID_RE.fullmatch(sid) or not any(p['steamid'] == sid for p in result['players']):
            raise HTTPException(404, "Player not found")
        return next(p for p in result['players'] if p['steamid'] == sid)

    def queue_explanation(self, job, owner, sid):
        self.player(job, owner, sid)
        with self.db() as db:
            db.execute("INSERT INTO explanations VALUES (?,?,'queued',NULL,?) ON CONFLICT(job,steamid) DO UPDATE SET state='queued',error_message=NULL,updated=excluded.updated WHERE explanations.state='failed'", (job, sid, now()))
            state = db.execute("SELECT state FROM explanations WHERE job=? AND steamid=?", (job, sid)).fetchone()['state']
        return {"state": state}

    def execute_explanation(self, row):
        job, sid = row['job'], row['steamid']
        with self.db() as db:
            db.execute("UPDATE explanations SET state='running',updated=? WHERE job=? AND steamid=?", (now(), job, sid))
        try:
            cmd = ([self.settings.PIPELINE_EXE, 'explain'] if self.settings.PIPELINE_EXE else
                   [str(self.settings.PYTHON_EXE), '-u', str(Path(__file__).with_name('pipeline_child.py')), str(self.settings.SCRIPTS_DIR / 'explain_demo.py')])
            cmd += ['--demo', job, '--steamid', sid, '--mode', 'infer']
            _, env = inference_command(self.settings, job, self.source(job))
            run_process(cmd, cwd=self.settings.PROJECT_ROOT, env=env,
                        log=self.report_dir(job) / 'logs' / f'explain_{sid}.log',
                        timeout=self.settings.EXPLAIN_TIMEOUT_SECONDS, on_stage=lambda _: None, stopping=self.stopping)
            report = json.loads((self.report_dir(job) / sid / 'report.json').read_text(encoding='utf8'))
            # Explicit public report allowlist. No raw debug traces are served.
            public = {k: report.get(k) for k in ('player','risk','confidence','uncertainty_ci','reasons','signals','evidence_files','interpretation')}
            public['evidence_files'] = [p.name for p in (self.report_dir(job) / sid).glob('evidence_*.csv') if EVIDENCE_RE.fullmatch(p.name)]
            write_json(self.report_dir(job) / sid / 'web_explanation.json', public)
            state, error = 'ready', None
        except Exception:
            logger.exception("Explanation failed for %s/%s", job, sid)
            state, error = 'failed', 'Explanation generation failed. Ranked results remain available; you may retry the explanation.'
        with self.db() as db:
            db.execute("UPDATE explanations SET state=?,error_message=?,updated=? WHERE job=? AND steamid=?", (state, error, now(), job, sid))


def service(request: Request) -> AnalysisService:
    instance = getattr(request.app.state, 'analysis', None)
    if instance is None:
        raise HTTPException(503, "Website analysis is not configured")
    if not instance.thread or not instance.thread.is_alive():
        raise HTTPException(503, "Analysis worker is unavailable")
    return instance


def owner(request: Request, svc: AnalysisService) -> str:
    supplied = request.headers.get('X-NULLCS-KEY', '')
    if not secrets.compare_digest(supplied, svc.settings.NULLCS_API_KEY):
        raise HTTPException(401, "Website gateway authentication required")
    value = request.headers.get('X-NULLCS-OWNER', '')
    if not re.fullmatch(r'[0-9a-f]{64}', value):
        raise HTTPException(401, "Website session required")
    return value


@router.get('/capabilities')
def capabilities(request: Request):
    svc = service(request)
    owner(request, svc)
    return {'max_upload_bytes': svc.settings.WEB_MAX_UPLOAD_BYTES, 'upload_transport': 'direct_worker'}


@router.post('')
def create_analysis(request: Request, metadata: UploadMetadata):
    svc = service(request)
    return svc.create(owner(request, svc), metadata)


@router.put('/{job}/upload')
async def upload_analysis(job: str, request: Request):
    svc = service(request)
    authorization = request.headers.get('Authorization', '')
    if not authorization.startswith('Bearer '):
        raise HTTPException(401, "Upload ticket required")
    row = await run_in_threadpool(svc.claim_upload, job, authorization[7:])
    partial = svc.partial(job)
    try:
        if request.headers.get('Content-Type', '').split(';')[0].lower() != 'application/octet-stream':
            raise HTTPException(415, "Upload must use application/octet-stream")
        length = request.headers.get('Content-Length')
        if length is not None and (not length.isdigit() or int(length) != row['size']):
            raise HTTPException(413, "Upload size does not match its reservation")
        partial.parent.mkdir(parents=True, exist_ok=True)
        total, prefix = 0, b''
        digest = hashlib.sha256()
        async with asyncio.timeout(svc.settings.WEB_UPLOAD_TIMEOUT_SECONDS):
            with partial.open('xb') as handle:
                async for chunk in request.stream():
                    total += len(chunk)
                    if total > row['size'] or total > svc.settings.WEB_MAX_UPLOAD_BYTES:
                        raise HTTPException(413, "Upload exceeds its reserved size")
                    if len(prefix) < 8:
                        prefix = (prefix + chunk)[:8]
                        if len(prefix) == 8 and prefix != b'PBDEMS2\x00':
                            raise HTTPException(400, "Expected a CS2 .dem replay; archives, executables and other formats are unsupported")
                    digest.update(chunk)
                    await run_in_threadpool(handle.write, chunk)
                if total != row['size'] or prefix != b'PBDEMS2\x00':
                    raise HTTPException(400, "Upload is incomplete or is not a CS2 replay")
        partial.replace(svc.source(job))
        svc.update(job, state='queued', stage='queued', upload_sha256=digest.hexdigest())
        return {'job_id': job, 'state': 'queued'}
    except BaseException as exc:
        svc.cleanup_upload(job)
        svc.update(job, state='failed', stage='failed', finished=now(), error_code='upload_failed', error_message='The upload failed or was incomplete. Please select the demo again.')
        if isinstance(exc, HTTPException):
            raise
        if isinstance(exc, asyncio.CancelledError):
            raise
        logger.exception("Upload failed for %s", job)
        raise HTTPException(503, "Upload could not be stored. Please try again.") from exc


@router.get('/{job}/status')
def analysis_status(job: str, request: Request):
    svc = service(request)
    return svc.status(job, owner(request, svc))


@router.get('/{job}/results')
def analysis_results(job: str, request: Request):
    svc = service(request)
    return svc.results(job, owner(request, svc))


@router.post('/{job}/players/{sid}/explain')
def analysis_explain(job: str, sid: str, request: Request):
    svc = service(request)
    return svc.queue_explanation(job, owner(request, svc), sid)


@router.get('/{job}/players/{sid}/explanation')
def analysis_explanation(job: str, sid: str, request: Request):
    svc = service(request)
    player = svc.player(job, owner(request, svc), sid)
    if player['explanation']['state'] != 'ready':
        return {'status': player['explanation'], 'report': None}
    try:
        report = json.loads((svc.report_dir(job) / sid / 'web_explanation.json').read_text(encoding='utf8'))
    except (OSError, ValueError):
        message = "Stored explanation is unavailable. Ranked results remain available; regenerate the explanation."
        logger.exception("Stored explanation unavailable for %s/%s", job, sid)
        with svc.db() as db:
            db.execute("UPDATE explanations SET state='failed',error_message=?,updated=? WHERE job=? AND steamid=? AND state='ready'",
                       (message, now(), job, sid))
        return {'status': {'state': 'failed', 'error': message}, 'report': None}
    return {'status': player['explanation'], 'report': report}


@router.get('/{job}/players/{sid}/evidence/{filename}')
def analysis_evidence(job: str, sid: str, filename: str, request: Request):
    svc = service(request)
    player = svc.player(job, owner(request, svc), sid)
    if player['explanation']['state'] != 'ready' or not EVIDENCE_RE.fullmatch(filename):
        raise HTTPException(404, "Evidence not found")
    path = svc.report_dir(job) / sid / filename
    if not path.is_file() or path.is_symlink():
        raise HTTPException(404, "Evidence not found")
    try:
        data = pd.read_csv(path, nrows=2001, dtype={k: str for k in ('steamid', 'attacker_steamid', 'victim_steamid', 'player_steamid')})
    except Exception:
        raise HTTPException(503, "Evidence could not be read")
    return clean({'filename': filename, 'columns': list(data.columns), 'rows': data.head(2000).to_dict(orient='records'), 'truncated': len(data) > 2000})

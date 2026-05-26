from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional local convenience
    load_dotenv = None

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from main.src.utils.project_paths import REPO_ROOT


def _load_local_env() -> None:
    if load_dotenv is None:
        return
    candidate_paths = [
        PROJECT_ROOT / ".env",
        PROJECT_ROOT / "main" / "ui" / "api" / ".env",
    ]
    for path in candidate_paths:
        if path.exists():
            load_dotenv(path, override=False)


_load_local_env()

PROJECT_ROOT = Path(os.getenv("NULLCS_PROJECT_ROOT", os.getenv("CLARITY_PROJECT_ROOT", str(REPO_ROOT))))
DEFAULT_VENV_PYTHON = PROJECT_ROOT / "NewAnubisTri" / ".venv" / "Scripts" / "python.exe"

def _is_healthy_python(candidate: str) -> bool:
    try:
        probe = subprocess.run(
            [candidate, "-c", "import pandas, polars, xgboost"],
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
        return probe.returncode == 0
    except Exception:
        return False


def _pick_python_exe() -> str:
    env_python = os.getenv("CLARITY_PYTHON_EXE", "").strip()
    if env_python:
        return env_python
    venv_python = str(DEFAULT_VENV_PYTHON)
    if DEFAULT_VENV_PYTHON.exists() and _is_healthy_python(venv_python):
        return venv_python
    return "python"


PYTHON_EXE = Path(_pick_python_exe())
PIPELINE_EXE = os.getenv("NULLCS_PIPELINE_EXE", "").strip()
APP_ENV = os.getenv("NULLCS_ENV", os.getenv("ENVIRONMENT", "development")).strip().lower()
IS_DESKTOP_MODE = os.getenv("NULLCS_DESKTOP_MODE", "0").strip().lower() in {"1", "true", "yes", "on"}
IS_PRODUCTION = APP_ENV == "production"
DEMO_MODE = os.getenv("NULLCS_DEMO_MODE", "0").strip().lower() in {"1", "true", "yes", "on"}
ENABLE_DIAGNOSTICS = os.getenv("NULLCS_ENABLE_DIAGNOSTICS", "0").strip().lower() in {"1", "true", "yes", "on"}
APP_MODE = "demo" if DEMO_MODE else ("desktop" if IS_DESKTOP_MODE else ("production" if IS_PRODUCTION else "local"))

DESKTOP_DATA_DIR_RAW = os.getenv("NULLCS_DESKTOP_DATA_DIR", "").strip()
DESKTOP_DATA_DIR = Path(DESKTOP_DATA_DIR_RAW) if DESKTOP_DATA_DIR_RAW else None
DEFAULT_DATA_ROOT = DESKTOP_DATA_DIR if (IS_DESKTOP_MODE and DESKTOP_DATA_DIR is not None) else PROJECT_ROOT / "main" / "data"

RAW_UPLOADS_DIR = Path(os.getenv("CLARITY_RAW_UPLOADS_DIR", str(DEFAULT_DATA_ROOT / "raw_uploads")))
UPLOAD_DIR = Path(os.getenv("NULLCS_UPLOAD_DIR", str(RAW_UPLOADS_DIR)))
PROCESSED_DIR = Path(os.getenv("CLARITY_PROCESSED_DIR", str(DEFAULT_DATA_ROOT / "processed")))
SCRIPTS_DIR = Path(os.getenv("CLARITY_SCRIPTS_DIR", str(PROJECT_ROOT / "main" / "scripts")))
MODEL_ARTIFACT = os.getenv("NULLCS_MODEL_ARTIFACT", os.getenv("CLARITY_MODEL_ARTIFACT", "")).strip()
NULLCS_API_KEY = os.getenv("NULLCS_API_KEY", "").strip()
NULLCS_DESKTOP_KEY = os.getenv("NULLCS_DESKTOP_KEY", "").strip()
FRONTEND_ORIGIN = os.getenv("NULLCS_FRONTEND_ORIGIN", "").strip()
MAX_UPLOAD_BYTES_RAW = os.getenv("NULLCS_MAX_UPLOAD_BYTES", "0").strip()
MAX_UPLOAD_BYTES = int(MAX_UPLOAD_BYTES_RAW) if MAX_UPLOAD_BYTES_RAW else 0
REQUEST_TIMEOUT_SECONDS = int(os.getenv("NULLCS_REQUEST_TIMEOUT_SECONDS", "30"))
JOB_TIMEOUT_SECONDS = int(os.getenv("NULLCS_JOB_TIMEOUT_SECONDS", str(30 * 60)))
EXPLAIN_TIMEOUT_SECONDS = int(os.getenv("NULLCS_EXPLAIN_TIMEOUT_SECONDS", "120"))
RATE_LIMIT_CAPACITY = int(os.getenv("NULLCS_RATE_LIMIT_CAPACITY", "30"))
RATE_LIMIT_REFILL_PER_SECOND = float(os.getenv("NULLCS_RATE_LIMIT_REFILL_PER_SECOND", "0.5"))

STATE_DIR = Path(os.getenv("NULLCS_STATE_DIR", str((DESKTOP_DATA_DIR / "state") if (IS_DESKTOP_MODE and DESKTOP_DATA_DIR is not None) else PROJECT_ROOT / "main" / "ui" / "api" / "state")))
JOBS_PATH = STATE_DIR / "jobs.json"

REPORTS_DIR = PROCESSED_DIR / "reports"
INFER_CSV = REPORTS_DIR / "ranked_player_demo_suspicion_infer.csv"


def model_version_label() -> str:
    if MODEL_ARTIFACT:
        return Path(MODEL_ARTIFACT).name
    return "default-local-model"

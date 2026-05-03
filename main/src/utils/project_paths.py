from __future__ import annotations

import os
from pathlib import Path


def _looks_like_repo_root(candidate: Path) -> bool:
    try:
        return candidate.is_dir() and (candidate / "main").is_dir() and (
            (candidate / "AGENTS.md").exists()
            or (candidate / ".git").exists()
            or (
                (candidate / ".nullcs-backend-root").exists()
                and (candidate / "main" / "ui" / "api" / "main.py").is_file()
                and (candidate / "main" / "scripts" / "run_infer_pipeline.py").is_file()
            )
        )
    except Exception:
        return False


def _iter_repo_candidates(start: str | Path | None = None):
    seen: set[str] = set()

    def walk(path_like: str | Path | None):
        if path_like is None:
            return
        try:
            path = Path(path_like)
            if path.is_file():
                path = path.parent
            chain = (path, *path.parents)
        except Exception:
            return
        for candidate in chain:
            key = os.path.normcase(str(candidate))
            if key in seen:
                continue
            seen.add(key)
            yield candidate

    env_root = os.getenv("NULLCS_PROJECT_ROOT", "").strip() or os.getenv("CLARITY_PROJECT_ROOT", "").strip()
    yield from walk(env_root or None)
    yield from walk(Path.cwd())
    yield from walk(start)
    if start is not None:
        try:
            yield from walk(Path(start).resolve())
        except Exception:
            pass


def find_repo_root(start: str | Path | None = None) -> Path:
    for candidate in _iter_repo_candidates(start if start is not None else __file__):
        if _looks_like_repo_root(candidate):
            return candidate
    raise RuntimeError(f"Could not resolve repo root from: {start if start is not None else __file__}")


REPO_ROOT = find_repo_root(__file__)
MAIN_ROOT = REPO_ROOT / "main"
PROCESSED_ROOT = MAIN_ROOT / "data" / "processed"
if os.getenv("CLARITY_PROCESSED_DIR", "").strip():
    PROCESSED_ROOT = Path(os.getenv("CLARITY_PROCESSED_DIR", "").strip())
REPORTS_ROOT = PROCESSED_ROOT / "reports"
MODELS_ROOT = PROCESSED_ROOT / "models"
DEMOS_ROOT = PROCESSED_ROOT / "demos"
PARSE_ZIPS_ROOT = PROCESSED_ROOT / "parse_zips"
PARSED_ZIPS_ROOT = REPO_ROOT / "parsed_zips"
PROCESSED_DEMOS_ROOT = REPO_ROOT / "processed" / "demos"
RAW_UPLOADS_ROOT = Path(os.getenv("NULLCS_UPLOAD_DIR", "").strip() or os.getenv("CLARITY_RAW_UPLOADS_DIR", "").strip() or str(MAIN_ROOT / "data" / "raw_uploads"))
HUGGFACE_DATA_ROOT = REPO_ROOT / "huggfacedata"
CHEATER_DEMOS_ROOT = REPO_ROOT / "CheaterDemos"
LEGIT_NORMAL_RENAMED_ROOT = REPO_ROOT / "LegitDemos" / "NormalRenamed"
LEGIT_PRO_RENAMED_ROOT = REPO_ROOT / "LegitDemos" / "ProsRenamed"


def newanubis_venv_python(repo_root: Path | None = None) -> Path:
    root = repo_root if repo_root is not None else REPO_ROOT
    return root / "NewAnubisTri" / ".venv" / "Scripts" / "python.exe"


def newanubis_awpy_exe(repo_root: Path | None = None) -> Path:
    root = repo_root if repo_root is not None else REPO_ROOT
    return root / "NewAnubisTri" / ".venv" / "Scripts" / "awpy.exe"

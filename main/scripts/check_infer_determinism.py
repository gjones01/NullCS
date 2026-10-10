from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.utils.project_paths import PROCESSED_ROOT


# demo_id shape the temporal (encounter-NN) loader can resolve; run_infer_pipeline.py validates
# it before parsing (see _validate_demo_id). The loader maps a TEST_/BENCH_ id to
# <upload root>/<demo_id>/<demo_id>.dem, which is exactly the copy run_infer_pipeline writes,
# so both runs stay resolvable while still being two distinct ids.
DEMO_ID_PREFIX = "TEST_"


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description=(
            "Run inference twice on same demo and assert deterministic raw_proba/model. "
            f"Both runs use a {DEMO_ID_PREFIX}... demo_id because the temporal loader only resolves "
            "upload-style ids (or an id whose demos/<demo_id>/meta.json points at a real demo)."
        )
    )
    ap.add_argument("--dem_path", required=True, help="Path to a .dem file")
    ap.add_argument("--out_dir", default=str(PROCESSED_ROOT))
    ap.add_argument("--model-artifact", default=None, help="Optional model artifact filename/path")
    return ap.parse_args()


def child_env(out_dir: Path) -> dict[str, str]:
    """Env for the child runs, pinning the upload root both processes resolve.

    run_infer_pipeline.py copies the demo to <NULLCS_UPLOAD_DIR or out_dir/../raw_uploads>/<demo_id>/<demo_id>.dem,
    while src/utils/project_paths.py resolves RAW_UPLOADS_ROOT from NULLCS_UPLOAD_DIR or
    main/data/raw_uploads. Those defaults disagree as soon as --out_dir is outside main/data, and the
    temporal loader then raises FileNotFoundError mid-run, so the root is passed down explicitly.
    """
    env = dict(os.environ)
    root = env.get("NULLCS_UPLOAD_DIR", "").strip() or env.get("CLARITY_RAW_UPLOADS_DIR", "").strip()
    if not root:
        root = str(out_dir.parent / "raw_uploads")
        env["NULLCS_UPLOAD_DIR"] = root
    return env


def run_once(
    dem_path: Path, out_dir: Path, demo_id: str, model_artifact: str | None, env: dict[str, str]
) -> Path:
    cmd = [
        sys.executable,
        str(Path(__file__).resolve().parent / "run_infer_pipeline.py"),
        "--dem_path",
        str(dem_path),
        "--demo_id",
        demo_id,
        "--out_dir",
        str(out_dir),
    ]
    if model_artifact:
        cmd.extend(["--model-artifact", model_artifact])
    print("[RUN]", " ".join(cmd))
    res = subprocess.run(cmd, check=False, env=env)
    if res.returncode != 0:
        raise RuntimeError(f"Inference run failed for {demo_id} with code {res.returncode}")
    return out_dir / "reports" / demo_id / "debug_score_trace.json"


def load_provenance(out_dir: Path, demo_id: str) -> dict:
    """Parser provenance stamped by run_infer_pipeline.py for one run (empty dict if absent)."""
    path = out_dir / "demos" / demo_id / "parser_provenance.json"
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def load_trace(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Missing debug trace: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def players_df(trace: dict) -> pd.DataFrame:
    rows = []
    for p in trace.get("players", []):
        rows.append(
            {
                "steamid": str(p.get("steamid", "")),
                "raw_proba": float(p.get("raw_proba", 0.0)),
                "model_artifact_path": str(p.get("model_artifact_path", "")),
                "model_sha256": str(p.get("model_sha256", "")),
            }
        )
    return pd.DataFrame(rows).sort_values("steamid").reset_index(drop=True)


def main() -> int:
    args = parse_args()
    dem_path = Path(args.dem_path).resolve()
    out_dir = Path(args.out_dir).resolve()
    if not dem_path.exists():
        raise FileNotFoundError(f"Demo file not found: {dem_path}")

    ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    demo_a = f"{DEMO_ID_PREFIX}{ts}_A"
    demo_b = f"{DEMO_ID_PREFIX}{ts}_B"

    env = child_env(out_dir)
    print(f"[INFO] upload root for both runs: {env.get('NULLCS_UPLOAD_DIR', '')}")
    trace_a_path = run_once(dem_path, out_dir, demo_a, args.model_artifact, env)
    trace_b_path = run_once(dem_path, out_dir, demo_b, args.model_artifact, env)

    ta = load_trace(trace_a_path)
    tb = load_trace(trace_b_path)
    da = players_df(ta)
    db = players_df(tb)
    prov_a = load_provenance(out_dir, demo_a)
    prov_b = load_provenance(out_dir, demo_b)

    merged = da.merge(db, on="steamid", suffixes=("_a", "_b"))
    if merged.empty:
        raise RuntimeError("No overlapping players across runs to compare.")

    same_model_path = (merged["model_artifact_path_a"] == merged["model_artifact_path_b"]).all()
    same_model_hash = (merged["model_sha256_a"] == merged["model_sha256_b"]).all()
    same_raw = (merged["raw_proba_a"].round(12) == merged["raw_proba_b"].round(12)).all()
    same_provenance = prov_a == prov_b

    print(f"[CHECK] same_model_path={bool(same_model_path)}")
    print(f"[CHECK] same_model_sha256={bool(same_model_hash)}")
    print(f"[CHECK] same_raw_proba={bool(same_raw)}")
    print(f"[CHECK] same_parser_provenance={bool(same_provenance)}")
    if not prov_a and not prov_b:
        print("[WARN] neither run recorded parser provenance; the score cannot be traced to a parser build")
    elif not same_provenance:
        print(f"[FAIL] run A provenance: {json.dumps(prov_a, sort_keys=True)}")
        print(f"[FAIL] run B provenance: {json.dumps(prov_b, sort_keys=True)}")

    if not (same_model_path and same_model_hash and same_raw and same_provenance):
        diffs = merged[
            (merged["model_artifact_path_a"] != merged["model_artifact_path_b"])
            | (merged["model_sha256_a"] != merged["model_sha256_b"])
            | (merged["raw_proba_a"].round(12) != merged["raw_proba_b"].round(12))
        ]
        if not diffs.empty:
            print(diffs.head(20).to_string(index=False))
        raise AssertionError("Determinism check failed.")

    print("[OK] Determinism check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

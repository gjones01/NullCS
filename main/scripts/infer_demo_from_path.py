from __future__ import annotations

import argparse
import hashlib
import io
import json
import subprocess
import sys
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
import os

import numpy as np
import pandas as pd
import polars as pl
from xgboost import XGBClassifier


PROJECT_ROOT = Path(__file__).resolve().parents[1]  # .../main
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.features.build_engagement_features import build_for_zip
import src.features.aggregate_player_features as agg_mod
from src.utils.scoring import (
    ensure_no_forbidden_features,
    compute_confidence_series,
    apply_rt_low_evidence_downweight,
    load_calibrator,
    maybe_calibrate,
    risk_band_series,
    top_signal_titles,
)
from src.utils.model_registry import resolve_model_artifacts
from src.utils.console import safe_print as _safe_print
from src.utils.parquet_io import write_df_to_parquet
from src.utils.project_paths import DEMOS_ROOT, MODELS_ROOT, PARSE_ZIPS_ROOT, PROCESSED_ROOT, REPORTS_ROOT


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Infer cheat suspicion for one raw .dem path.")
    ap.add_argument("--dem", required=True, help="Path to raw .dem file (no rename required).")
    ap.add_argument("--steamid", default=None, help="Optional Steam64 to explain. Defaults to top-1 in lobby.")
    ap.add_argument(
        "--model-artifact",
        default=None,
        help="Optional model artifact filename/path. Default: newest model in processed/models.",
    )
    return ap.parse_args()


def make_demo_id(dem_path: Path) -> str:
    now = datetime.now().strftime("%Y%m%d_%H%M%S")
    h = hashlib.sha1(str(dem_path.resolve()).encode("utf-8")).hexdigest()[:8]
    return f"TEST_{now}_{h}"


def parse_dem_to_zip(dem_path: Path, zip_path: Path) -> None:
    from awpy import Demo

    zip_path.parent.mkdir(parents=True, exist_ok=True)
    _safe_print(f"[PARSE] {dem_path}")
    demo = Demo(str(dem_path))
    demo.parse()

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        tables_written: list[str] = []

        def try_write(name: str, getter) -> None:
            try:
                df = getter()
                write_df_to_parquet(df, tmpdir / f"{name}.parquet")
                tables_written.append(f"{name}.parquet")
            except KeyError:
                _safe_print(f"  [SKIP] {name} (missing required event in demo)")
            except Exception as e:
                _safe_print(f"  [WARN] {name} failed: {e}")

        try_write("kills", lambda: demo.kills)
        try_write("damages", lambda: demo.damages)
        try_write("shots", lambda: demo.shots)
        try_write("grenades", lambda: demo.grenades)
        try_write("smokes", lambda: demo.smokes)
        try_write("infernos", lambda: demo.infernos)
        try_write("bomb", lambda: demo.bomb)
        try_write("ticks", lambda: demo.ticks)
        try_write("rounds", lambda: demo.rounds)
        try_write("footsteps", lambda: demo.footsteps)

        header_path = tmpdir / "header.json"
        header_obj = demo.header
        if hasattr(header_obj, "model_dump"):
            header_obj = header_obj.model_dump()
        elif hasattr(header_obj, "dict"):
            header_obj = header_obj.dict()
        header_path.write_text(json.dumps(header_obj, indent=2), encoding="utf-8")
        tables_written.append("header.json")

        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for fname in tables_written:
                zf.write(tmpdir / fname, arcname=fname)

    _safe_print(f"[OK] parsed zip: {zip_path}")


def build_engagement_for_demo(demo_id: str, zip_path: Path) -> Path:
    out_dir = DEMOS_ROOT / demo_id
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "engagement_features.parquet"

    _safe_print(f"[BUILD] engagement features for {demo_id}")
    eng = build_for_zip(zip_path)
    if "attacker_steamid" in eng.columns:
        eng = eng.with_columns(pl.col("attacker_steamid").cast(pl.Utf8))
    if "victim_steamid" in eng.columns:
        eng = eng.with_columns(pl.col("victim_steamid").cast(pl.Utf8))
    eng.write_parquet(out_path)
    _safe_print(f"[OK] wrote engagement: {out_path}")
    return out_path


def aggregate_single_demo_features(demo_id: str, eng_path: Path, encounter_path: Path | None = None) -> pd.DataFrame:
    """Aggregate one demo with the canonical training-time aggregator.

    Delegates to ``aggregate_player_features.aggregate_kill_and_encounter_frames``
    so inference features cannot drift from training features (AUDIT.md finding F4).
    This function previously carried ~122 lines of copied derived-feature math
    (laplace rates, weapon splits, *_w, rt_iqr_80, dist_tail, *_shrunk, demo norms).

    ``encounter_path`` is optional. When it is None the encounter (``enc_*``)
    columns are absent and are filled with 0.0 at scoring time, exactly as before.
    ``run_infer_pipeline.py`` is the reference caller: it scores encounter windows
    first and then passes them in.
    """
    df = pd.read_parquet(eng_path)
    if df.empty:
        raise RuntimeError(f"No engagement rows found for demo {demo_id}.")

    required = ("attacker_steamid", "kill_tick", "rt_ticks", "distance")
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Engagement features missing {missing} for demo {demo_id}: {eng_path}")

    df = df.copy()
    df["demo_id"] = str(demo_id)
    df["label"] = 0
    df["attacker_steamid"] = df["attacker_steamid"].astype(str).str.strip()
    for col, default in [
        ("map_name", ""),
        ("attacker_name", ""),
        ("victim_steamid", ""),
        ("weapon", ""),
        ("headshot", False),
        ("is_thrusmoke", False),
        ("is_micropeek_4", False),
        ("round_num", np.nan),
    ]:
        if col not in df.columns:
            df[col] = default

    encounter_df = pd.DataFrame()
    if encounter_path is not None and Path(encounter_path).exists():
        candidate = pd.read_parquet(encounter_path)
        if candidate is not None and not candidate.empty:
            encounter_df = candidate.copy()
            encounter_df["demo_id"] = str(demo_id)
            encounter_df["label"] = 0
            encounter_df["attacker_steamid"] = encounter_df["attacker_steamid"].astype(str).str.strip()
            if "attacker_name" not in encounter_df.columns:
                encounter_df["attacker_name"] = ""

    agg = agg_mod.aggregate_kill_and_encounter_frames(df, encounter_df)
    if agg.empty:
        raise RuntimeError(
            f"No players pass MIN_KILLS={agg_mod.MIN_KILLS} in demo {demo_id}. "
            "Cannot score with training-compatible features."
        )
    return agg


def score_demo(agg: pd.DataFrame, model_artifact: str | None = None) -> pd.DataFrame:
    requested_model = model_artifact or os.environ.get("CLARITY_MODEL_ARTIFACT")
    model_path, features_path = resolve_model_artifacts(MODELS_ROOT, requested_model)
    feature_cols = features_path.read_text(encoding="utf-8").strip().splitlines()
    ensure_no_forbidden_features(feature_cols, str(features_path))
    missing_features = [c for c in feature_cols if c not in agg.columns]
    for c in missing_features:
        agg[c] = np.nan
    if missing_features:
        # Was silent before: absent contract features are scored as 0.0. Keep the
        # behaviour (so this path stays comparable to earlier runs) but report it.
        _safe_print(
            f"[WARN] {len(missing_features)}/{len(feature_cols)} contract features are absent from this demo's "
            f"aggregation and will be scored as 0.0 (first 8: {missing_features[:8]}). "
            "The enc_* family requires the encounter-model step; see run_infer_pipeline.py."
        )

    X = agg[feature_cols].fillna(0.0).astype(float)
    model = XGBClassifier()
    model.load_model(str(model_path))
    proba = model.predict_proba(X)[:, 1]

    ranked = agg.copy()
    ranked["attacker_steamid"] = ranked["attacker_steamid"].astype(str).str.strip()
    ranked["proba_cheater_infer"] = proba
    ranked["confidence"] = compute_confidence_series(ranked)
    calibrator = load_calibrator()
    ranked["proba_calibrated"] = np.nan
    if calibrator is not None:
        ranked["proba_calibrated"] = maybe_calibrate(ranked["proba_cheater_infer"], calibrator)
    risk_base = ranked["proba_calibrated"].copy()
    miss = risk_base.isna()
    risk_base.loc[miss] = ranked.loc[miss, "proba_cheater_infer"].astype(float)
    ranked["risk"] = apply_rt_low_evidence_downweight(risk_base, ranked.get("rt_n", pd.Series([0] * len(ranked))))
    ranked["risk_band"] = risk_band_series(ranked["risk"])
    ranked["rt_reason_confidence"] = np.where(ranked.get("rt_n", pd.Series([0] * len(ranked))).fillna(0).astype(float) < 8, "low", "normal")
    ranked["ci_low"] = np.nan
    ranked["ci_high"] = np.nan
    ranked["top_reasons"] = ranked.apply(lambda r: json.dumps(top_signal_titles(r, top_k=3)), axis=1)
    ranked = ranked.sort_values("risk", ascending=False).reset_index(drop=True)
    return ranked


def write_ranked_outputs(demo_id: str, ranked: pd.DataFrame) -> tuple[Path, Path]:
    REPORTS_ROOT.mkdir(parents=True, exist_ok=True)
    demo_report_dir = REPORTS_ROOT / demo_id
    demo_report_dir.mkdir(parents=True, exist_ok=True)

    global_ranked = REPORTS_ROOT / "ranked_player_demo_suspicion_infer.csv"
    demo_ranked = demo_report_dir / "ranked_player_demo_suspicion_infer.csv"
    ranked.to_csv(global_ranked, index=False)
    ranked.to_csv(demo_ranked, index=False)
    return global_ranked, demo_ranked


def run_explain(demo_id: str, steamid: str | None) -> None:
    cmd = [sys.executable, str(PROJECT_ROOT / "scripts" / "explain_demo.py"), "--demo", demo_id, "--mode", "infer"]
    if steamid:
        cmd.extend(["--steamid", str(steamid).strip()])
    _safe_print(f"[EXPLAIN] {' '.join(cmd)}")
    res = subprocess.run(cmd, check=False, text=True, capture_output=True)
    if res.stdout:
        print(res.stdout)
    if res.stderr:
        print(res.stderr)
    if res.returncode != 0:
        raise RuntimeError(f"Explain command failed with exit code {res.returncode}")


def main() -> int:
    args = parse_args()
    dem_path = Path(args.dem).expanduser().resolve()
    if not dem_path.exists() or dem_path.suffix.lower() != ".dem":
        raise FileNotFoundError(f"Expected an existing .dem file path, got: {dem_path}")

    demo_id = make_demo_id(dem_path)
    zip_path = PARSE_ZIPS_ROOT / f"{demo_id}.zip"

    parse_dem_to_zip(dem_path, zip_path)
    eng_path = build_engagement_for_demo(demo_id, zip_path)
    agg = aggregate_single_demo_features(demo_id, eng_path)
    ranked = score_demo(agg, model_artifact=args.model_artifact)
    global_ranked, demo_ranked = write_ranked_outputs(demo_id, ranked)

    _safe_print(f"[OK] wrote inference ranked CSV: {demo_ranked}")
    _safe_print(f"[OK] refreshed explain source CSV: {global_ranked}")
    run_explain(demo_id, args.steamid)
    _safe_print(f"[DONE] reports at: {REPORTS_ROOT / demo_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

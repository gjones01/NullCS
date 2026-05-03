from __future__ import annotations

import argparse
import importlib.util
import hashlib
import json
import shutil
import sys
from pathlib import Path
import os

import numpy as np
import pandas as pd
from xgboost import XGBClassifier

# Ensure "main/" is importable.
MAIN_ROOT = Path(__file__).resolve().parents[1]
sys.path = [p for p in sys.path if "ClarityCS\\main" not in str(p)]
if str(MAIN_ROOT) in sys.path:
    sys.path.remove(str(MAIN_ROOT))
sys.path.insert(0, str(MAIN_ROOT))
for mod_name in list(sys.modules):
    if mod_name == "src" or mod_name.startswith("src."):
        sys.modules.pop(mod_name, None)
src_init = MAIN_ROOT / "src" / "__init__.py"
src_spec = importlib.util.spec_from_file_location("src", src_init, submodule_search_locations=[str(MAIN_ROOT / "src")])
if src_spec is None or src_spec.loader is None:
    raise RuntimeError(f"Could not bootstrap local src package from {src_init}")
src_module = importlib.util.module_from_spec(src_spec)
sys.modules["src"] = src_module
src_spec.loader.exec_module(src_module)

from src.features import build_cs2cd_engagement_features as cs2cd_build_mod
from src.features import aggregate_player_features as agg_mod
from src.adapters.demoparser2_local import load_demo as load_demoparser2_demo
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
from src.utils.project_paths import RAW_UPLOADS_ROOT
from src.models.encounter_nn import (
    encounter_infer_player_feature_path,
    encounter_model_artifacts,
    load_trained_encounter_model,
    score_encounter_frame,
    aggregate_encounter_scores,
)


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Inference-only pipeline for one demo.")
    ap.add_argument("--dem_path", required=True, help="Path to input .dem file")
    ap.add_argument("--demo_id", required=True, help="Demo ID, e.g. TEST_YYYYMMDD_HHMMSS_abcd1234")
    ap.add_argument(
        "--out_dir",
        required=True,
        help="Processed root output directory, e.g. C:\\ClarityCS\\main\\data\\processed",
    )
    ap.add_argument(
        "--model-artifact",
        default=None,
        help="Optional model artifact filename/path. Default: newest model in processed/models.",
    )
    return ap.parse_args()


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _feature_vector_hash(row: pd.Series, feature_cols: list[str]) -> str:
    vals = []
    for c in feature_cols:
        v = row.get(c, np.nan)
        if pd.isna(v):
            vals.append(None)
        else:
            vals.append(float(v))
    payload = json.dumps(vals, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _write_table(df, path: Path) -> None:
    if hasattr(df, "write_parquet"):
        df.write_parquet(path)
        return
    if hasattr(df, "to_parquet"):
        df.to_parquet(path, index=False)
        return
    raise TypeError(f"Unsupported table type for parquet write: {type(df).__name__}")


def _high_tag_flags(row: pd.Series) -> dict[str, bool]:
    out = {}
    for c in ["prefire_pct", "thrusmoke_pct", "hs_pct", "long_fast_rt_pct"]:
        v = row.get(c, np.nan)
        out[c] = bool(pd.notna(v) and float(v) >= 0.90)
    return out


def _ensure_demo_copy(src_dem: Path, demo_id: str, raw_uploads_root: Path) -> Path:
    if src_dem.suffix.lower() != ".dem":
        raise ValueError(f"Input must be a .dem file: {src_dem}")
    if not src_dem.exists():
        raise FileNotFoundError(f"Demo file not found: {src_dem}")

    dst_dir = raw_uploads_root / demo_id
    dst_dir.mkdir(parents=True, exist_ok=True)
    dst_dem = dst_dir / f"{demo_id}.dem"
    if src_dem.resolve() != dst_dem.resolve():
        shutil.copy2(src_dem, dst_dem)
    return dst_dem


def _build_player_features_for_demo(engagement_path: Path, demo_id: str, encounter_path: Path | None = None) -> pd.DataFrame:
    df = pd.read_parquet(engagement_path)
    if df.empty:
        raise RuntimeError(f"Engagement features are empty for demo: {demo_id}")

    if "attacker_steamid" not in df.columns:
        raise ValueError(f"Missing attacker_steamid in engagement features: {engagement_path}")

    df = df.copy()
    df["demo_id"] = demo_id
    df["label"] = -1  # placeholder for inference-only rows
    df["attacker_steamid"] = df["attacker_steamid"].astype(str).str.strip()
    if "attacker_name" not in df.columns:
        df["attacker_name"] = ""

    encounter_df = pd.DataFrame()
    if encounter_path is not None and encounter_path.exists():
        encounter_df = pd.read_parquet(encounter_path)
        if not encounter_df.empty:
            encounter_df = encounter_df.copy()
            encounter_df["demo_id"] = demo_id
            encounter_df["label"] = -1
            encounter_df["attacker_steamid"] = encounter_df["attacker_steamid"].astype(str).str.strip()
            if "attacker_name" not in encounter_df.columns:
                encounter_df["attacker_name"] = ""

    agg = agg_mod.aggregate_kill_and_encounter_frames(df, encounter_df)
    if agg.empty:
        raise RuntimeError(f"No eligible players (MIN_KILLS filter) for demo: {demo_id}")
    return agg


def _merge_encounter_features_for_demo(player_df: pd.DataFrame, encounter_path: Path) -> pd.DataFrame:
    if not encounter_path.exists():
        return player_df

    encounters = pd.read_parquet(encounter_path)
    if encounters.empty:
        return player_df

    encounters = encounters.copy()
    for col, default in [
        ("demo_id", player_df["demo_id"].iloc[0] if not player_df.empty else ""),
        ("map_name", ""),
        ("attacker_steamid", ""),
        ("attacker_name", ""),
        ("label", -1),
        ("start_tick", np.nan),
        ("exposure_duration", np.nan),
        ("visible_ratio", np.nan),
        ("time_to_first_shot", np.nan),
        ("time_to_first_damage", np.nan),
        ("aim_error_at_first_visible", np.nan),
        ("aim_error_min", np.nan),
        ("aim_acquire_time", np.nan),
        ("aim_dwell_ticks", np.nan),
        ("shot_before_aim_acquire", False),
        ("shot_count", np.nan),
        ("shot_rate_per_128", np.nan),
        ("mean_shot_gap", np.nan),
        ("damage_count", np.nan),
        ("damage_total", np.nan),
        ("ended_in_damage", False),
        ("angular_velocity_mean", np.nan),
        ("angular_jerk_mean", np.nan),
        ("los_angular_velocity_mean", np.nan),
        ("los_angular_jerk_mean", np.nan),
        ("distance_mean", np.nan),
        ("closing_speed_mean", np.nan),
        ("attacker_speed_mean", np.nan),
        ("victim_speed_mean", np.nan),
        ("relative_speed_mean", np.nan),
        ("ended_in_kill_within_y", False),
    ]:
        if col not in encounters.columns:
            encounters[col] = default
    encounters["label"] = -1

    encounters["attacker_steamid"] = encounters["attacker_steamid"].astype(str).str.strip()
    # Do not key on attacker_name for inference merges. Name encoding / normalization can differ
    # between kill and encounter paths even when the SteamID is the same.
    key_cols = ["demo_id", "map_name", "attacker_steamid", "label"]
    enc_rows = [agg_mod.build_encounter_row(g) for _, g in encounters.groupby(key_cols, sort=False)]
    enc_agg = pd.DataFrame(enc_rows)
    if enc_agg.empty:
        return player_df
    if "attacker_name" in enc_agg.columns:
        enc_agg = enc_agg.drop(columns=["attacker_name"])
    return player_df.merge(enc_agg, on=key_cols, how="left")


def _merge_encounter_nn_features_for_demo(
    player_df: pd.DataFrame,
    encounter_df: pd.DataFrame,
    processed_root: Path,
    train_mode: str,
) -> pd.DataFrame:
    artifacts = encounter_model_artifacts(processed_root / "models", train_mode)
    if not artifacts["model"].exists() or not artifacts["manifest"].exists():
        return player_df
    if encounter_df.empty:
        return player_df
    try:
        manifest = json.loads(artifacts["manifest"].read_text(encoding="utf-8"))
        if manifest.get("max_demos") not in (None, ""):
            print("[WARN] encounter NN artifact came from a capped smoke run; skipping stack features in inference")
            return player_df
        model, preproc, feature_cols, device_name = load_trained_encounter_model(
            artifacts["model"], artifacts["preproc"], artifacts["features"]
        )
        scored = score_encounter_frame(encounter_df, model, preproc, feature_cols, device=device_name)
        player_scores = aggregate_encounter_scores(scored)
        if player_scores.empty:
            return player_df
        out_path = encounter_infer_player_feature_path(processed_root, str(player_df["demo_id"].iloc[0]))
        out_path.parent.mkdir(parents=True, exist_ok=True)
        player_scores.to_parquet(out_path, index=False)
        merged = player_df.merge(player_scores, on=["demo_id", "attacker_steamid"], how="left")
        print(f"[OK] wrote {out_path}")
        return merged
    except Exception as exc:
        print(f"[WARN] encounter NN scoring skipped: {exc}")
        return player_df


def _selected_train_mode(models_dir: Path, model_artifact: str | None) -> tuple[Path, Path, str]:
    model_path, feats_path = resolve_model_artifacts(models_dir, model_artifact)
    manifest_path = model_path.with_name(f"{model_path.stem}_training_manifest.json")
    train_mode = "merged"
    if manifest_path.exists():
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            train_mode = str(payload.get("train_data_mode", train_mode)).strip().lower() or train_mode
        except Exception:
            pass
    return model_path, feats_path, train_mode


def _build_demo_feature_frames_demoparser2(demo_file: Path, demo_id: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    match = load_demoparser2_demo(demo_file, demo_id=demo_id)
    kill_df, encounter_df = cs2cd_build_mod.build_match_outputs(match)
    return kill_df, encounter_df


def _infer_scores(
    player_df: pd.DataFrame,
    processed_root: Path,
    model_artifact: str | None = None,
) -> tuple[pd.DataFrame, dict[str, object]]:
    models_dir = processed_root / "models"
    reports_dir = processed_root / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    requested_model = model_artifact or os.environ.get("NULLCS_MODEL_ARTIFACT") or os.environ.get("CLARITY_MODEL_ARTIFACT")
    model_path, feats_path = resolve_model_artifacts(models_dir, requested_model)
    model_hash = _sha256_file(model_path)
    feats_hash = _sha256_file(feats_path)

    feature_cols = [x for x in feats_path.read_text(encoding="utf-8").splitlines() if x.strip()]
    ensure_no_forbidden_features(feature_cols, str(feats_path))
    for c in feature_cols:
        if c not in player_df.columns:
            player_df[c] = np.nan

    X = player_df[feature_cols].fillna(0.0).astype(float)
    model = XGBClassifier()
    model.load_model(str(model_path))
    scores = model.predict_proba(X)[:, 1]

    out = player_df.copy()
    out["model_artifact_path"] = str(model_path)
    out["model_artifact_sha256"] = model_hash
    out["feature_list_path"] = str(feats_path)
    out["feature_list_sha256"] = feats_hash
    out["feature_list_version"] = feats_hash[:12]
    out["proba_cheater_infer"] = scores
    out["confidence"] = compute_confidence_series(out)
    calibrator = load_calibrator(model_path=model_path)
    out["proba_calibrated"] = np.nan
    if calibrator is not None:
        out["proba_calibrated"] = maybe_calibrate(out["proba_cheater_infer"], calibrator)
    risk_base = out["proba_calibrated"].copy()
    miss = risk_base.isna()
    risk_base.loc[miss] = out.loc[miss, "proba_cheater_infer"].astype(float)
    out["risk"] = apply_rt_low_evidence_downweight(risk_base, out.get("rt_n", pd.Series([0] * len(out))))
    out["risk_band"] = risk_band_series(out["risk"], out.get("rt_n"), out.get("n_kills_with_rt"), out.get("confidence"))
    out["rt_reason_confidence"] = np.where(out.get("rt_n", pd.Series([0] * len(out))).fillna(0).astype(float) < 8, "low", "normal")
    out["ci_low"] = np.nan
    out["ci_high"] = np.nan
    out["top_reasons"] = out.apply(lambda r: json.dumps(top_signal_titles(r, top_k=3)), axis=1)
    out = out.sort_values("risk", ascending=False)

    trace_players: list[dict[str, object]] = []
    for _, r in out.iterrows():
        pct_cols = [c for c in out.columns if c.endswith("_pct")]
        z_cols = [c for c in out.columns if c.endswith("_z")]
        lobby_pct = {c: (None if pd.isna(r.get(c)) else float(r.get(c))) for c in pct_cols}
        lobby_z = {c: (None if pd.isna(r.get(c)) else float(r.get(c))) for c in z_cols}
        feat_row = {}
        for c in feature_cols:
            v = r.get(c, np.nan)
            feat_row[c] = None if pd.isna(v) else float(v)

        raw = float(r.get("proba_cheater_infer", 0.0))
        cal = None if pd.isna(r.get("proba_calibrated")) else float(r.get("proba_calibrated"))
        risk = float(r.get("risk", 0.0))
        rt_n = float(r.get("rt_n", 0.0) if pd.notna(r.get("rt_n")) else 0.0)
        nkrt = float(r.get("n_kills_with_rt", 0.0) if pd.notna(r.get("n_kills_with_rt")) else 0.0)
        n_players = float(r.get("n_players", 0.0) if pd.notna(r.get("n_players")) else 0.0)
        low_evidence_fired = bool(rt_n < 8.0)
        high_tags = _high_tag_flags(r)
        any_high_tag = any(high_tags.values())
        why_low = None
        if any_high_tag and risk < 0.20:
            reasons = []
            if low_evidence_fired:
                reasons.append("low RT evidence downweight fired (rt_n < 8)")
            if cal is not None and cal < raw:
                reasons.append("calibration reduced probability")
            if not reasons:
                reasons.append("model base probability is low despite high percentile tags")
            why_low = "; ".join(reasons)

        trace_players.append(
            {
                "steamid": str(r.get("attacker_steamid", "")),
                "attacker_name": str(r.get("attacker_name", "")),
                "model_artifact_path": str(model_path),
                "model_version": model_hash[:12],
                "model_sha256": model_hash,
                "feature_list_path": str(feats_path),
                "feature_list_version": feats_hash[:12],
                "feature_list_sha256": feats_hash,
                "feature_row": feat_row,
                "feature_vector_hash": _feature_vector_hash(r, feature_cols),
                "raw_proba": raw,
                "calibrated_proba": cal,
                "lobby_percentile": lobby_pct,
                "lobby_z": lobby_z,
                "risk_display_value": risk,
                "risk_display_value_pct": risk * 100.0,
                "confidence_value": float(r.get("confidence", 0.0)),
                "confidence_value_pct": float(r.get("confidence", 0.0)) * 100.0,
                "confidence_method": (
                    "compute_confidence = 0.45*log1p(n_kills_with_rt)/log1p(30)"
                    " + 0.35*log1p(rt_n)/log1p(30)"
                    " + 0.20*log1p(rounds_played)/log1p(24), clipped to [0,1]"
                ),
                "ci_p05": (None if pd.isna(r.get("ci_low")) else float(r.get("ci_low"))),
                "ci_p95": (None if pd.isna(r.get("ci_high")) else float(r.get("ci_high"))),
                "ci_method": "not computed in current inference path (ci_low/ci_high are NaN)",
                "gating_rules": {
                    "low_evidence_downweight_fired": low_evidence_fired,
                    "n_kills_with_rt_thresholding_applied": True,
                    "n_kills_with_rt_value": nkrt,
                    "n_players_filter_applied": False,
                    "n_players_filter_note": "n_players>=8 filter is used in offline training/eval, not single-demo inference",
                    "n_players_value": n_players,
                },
                "evidence_counts": {
                    "rt_n": rt_n,
                    "smoke_n": float(r.get("smoke_n", 0.0) if pd.notna(r.get("smoke_n")) else 0.0),
                    "hs_n": float(r.get("hs_n", 0.0) if pd.notna(r.get("hs_n")) else 0.0),
                    "prefire_n": float(r.get("prefire_count", 0.0) if pd.notna(r.get("prefire_count")) else 0.0),
                    "long_range_n": float(
                        r.get("long_range_kills_with_rt", 0.0) if pd.notna(r.get("long_range_kills_with_rt")) else 0.0
                    ),
                },
                "high_tag_flags": high_tags,
                "why_risk_low_despite_high_tags": why_low,
            }
        )

    debug_trace = {
        "demo_id": str(player_df["demo_id"].iloc[0]),
        "model_artifact_path": str(model_path),
        "model_sha256": model_hash,
        "feature_list_path": str(feats_path),
        "feature_list_sha256": feats_hash,
        "risk_formula": "risk = calibrated_proba if available else raw_proba; then downweight by 0.85 when rt_n < 8",
        "confidence_formula": (
            "0.45*log1p(n_kills_with_rt)/log1p(30) + "
            "0.35*log1p(rt_n)/log1p(30) + "
            "0.20*log1p(rounds_played)/log1p(24), clamp to [0,1]"
        ),
        "calibration_used": bool(calibrator is not None),
        "ci_method": "not computed in current inference path",
        "players": trace_players,
    }

    infer_csv = reports_dir / "ranked_player_demo_suspicion_infer.csv"
    if infer_csv.exists():
        old = pd.read_csv(infer_csv)
        old = old[old["demo_id"].astype(str) != str(player_df["demo_id"].iloc[0])]
        out_all = pd.concat([old, out], ignore_index=True)
        sort_col = "risk" if "risk" in out_all.columns else "proba_cheater_infer"
        out_all = out_all.sort_values(sort_col, ascending=False)
    else:
        out_all = out
    out_all.to_csv(infer_csv, index=False)
    print(f"[OK] wrote {infer_csv}")
    return out, debug_trace


def main() -> int:
    args = parse_args()
    dem_path = Path(args.dem_path)
    demo_id = str(args.demo_id).strip()
    processed_root = Path(args.out_dir)
    if not demo_id:
        raise ValueError("demo_id cannot be empty")

    raw_uploads_root = Path(
        os.environ.get("NULLCS_UPLOAD_DIR")
        or os.environ.get("CLARITY_RAW_UPLOADS_DIR")
        or str(processed_root.parent / "raw_uploads")
    )
    demos_root = processed_root / "demos"
    reports_root = processed_root / "reports"
    models_dir = processed_root / "models"

    demo_file = _ensure_demo_copy(dem_path, demo_id, raw_uploads_root)
    print(f"[INFO] demo file: {demo_file}")
    model_path, _feats_path, train_mode = _selected_train_mode(models_dir, args.model_artifact)
    print(f"[INFO] selected model: {model_path.name} train_mode={train_mode}")

    parse_warning = None
    encounter_warning = None
    parser_mode = "demoparser2_local"
    if train_mode != "cs2cd":
        print(f"[WARN] model train_mode={train_mode}; demo will still be parsed with demoparser2-local for schema parity")

    kill_df, encounter_df = _build_demo_feature_frames_demoparser2(demo_file, demo_id=demo_id)
    print("[INFO] parsed demo with demoparser2-local")

    demo_dir = demos_root / demo_id
    demo_dir.mkdir(parents=True, exist_ok=True)
    eng_path = demo_dir / "engagement_features.parquet"
    encounter_path = demo_dir / "encounters.parquet"
    _write_table(kill_df, eng_path)
    _write_table(encounter_df, encounter_path)
    print(f"[OK] wrote {eng_path}")
    print(f"[OK] wrote {encounter_path}")

    player_df = _build_player_features_for_demo(eng_path, demo_id=demo_id, encounter_path=encounter_path)
    player_df = _merge_encounter_nn_features_for_demo(player_df, encounter_df, processed_root, train_mode)
    per_demo_player_path = demo_dir / "player_features_infer.parquet"
    player_df.to_parquet(per_demo_player_path, index=False)
    print(f"[OK] wrote {per_demo_player_path}")

    infer_ranked, debug_trace = _infer_scores(player_df, processed_root=processed_root, model_artifact=args.model_artifact)
    per_demo_report_dir = reports_root / demo_id
    per_demo_report_dir.mkdir(parents=True, exist_ok=True)
    per_demo_csv = per_demo_report_dir / "ranked_players_infer.csv"
    infer_ranked.to_csv(per_demo_csv, index=False)
    print(f"[OK] wrote {per_demo_csv}")
    debug_trace_path = per_demo_report_dir / "debug_score_trace.json"
    debug_trace_path.write_text(json.dumps(debug_trace, indent=2), encoding="utf-8")
    print(f"[OK] wrote {debug_trace_path}")

    manifest = {
        "demo_id": demo_id,
        "demo_file": str(demo_file),
        "zip_path": "",
        "parser_mode": parser_mode,
        "parse_warning": parse_warning,
        "engagement_features": str(eng_path),
        "encounters": str(encounter_path),
        "encounter_build_warning": encounter_warning,
        "player_features_infer": str(per_demo_player_path),
        "ranked_players_infer": str(per_demo_csv),
        "debug_score_trace": str(debug_trace_path),
        "model_artifact_path": str(debug_trace.get("model_artifact_path", "")),
        "model_sha256": str(debug_trace.get("model_sha256", "")),
    }
    manifest_path = per_demo_report_dir / "infer_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"[OK] wrote {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

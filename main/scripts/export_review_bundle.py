from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
import sys
from typing import Any

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.utils.explain_demo import (  # noqa: E402
    _build_signals,
    _normalize_steamid_series,
    _parse_top_reasons_field,
    _read_ranked,
    _safe_float,
    build_reasons,
    default_config,
    load_demo_context,
)
from src.utils.behavioral_context import build_demo_interpretations  # noqa: E402
from src.utils.project_paths import PROCESSED_ROOT  # noqa: E402


DEFAULT_SUMMARY_KEYS = (
    "rt_median",
    "prefire_rate",
    "thrusmoke_kill_rate",
    "headshot_rate",
    "long_range_fast_rt_rate_4",
    "enc_aim_error_min_median",
    "enc_aim_acquire_median",
    "enc_ang_vel_median",
)

SAFE_TRACE_FEATURE_KEYS = (
    "rt_median",
    "rt_p10",
    "rt_p90",
    "prefire_rate",
    "headshot_rate",
    "thrusmoke_kill_rate",
    "long_range_fast_rt_rate_4",
    "enc_aim_error_min_median",
    "enc_aim_acquire_median",
    "enc_ang_vel_median",
)


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Export a desktop-safe NullCS review bundle.")
    ap.add_argument("--demo", required=True, help="Demo ID to export.")
    ap.add_argument("--mode", choices=["infer", "oof", "insample"], default="infer", help="Ranked file mode.")
    ap.add_argument("--top", type=int, default=5, help="How many top-ranked players to include.")
    ap.add_argument("--rows-per-evidence", type=int, default=30, help="Max rows per evidence table.")
    ap.add_argument(
        "--benchmark-summary",
        default=str(PROCESSED_ROOT / "reports" / "benchmark_suite_20260329_162143" / "benchmark_suite_summary.json"),
        help="Optional benchmark summary JSON to embed as a compact snapshot.",
    )
    ap.add_argument(
        "--output",
        default=None,
        help="Optional output path. Default: main/data/processed/review_bundles/<demo>_<mode>.json",
    )
    return ap.parse_args()


def _safe_json_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return value if pd.notna(value) else None
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            if "path" in key_text.lower():
                continue
            out[key_text] = _safe_json_value(item)
        return out
    if isinstance(value, list):
        return [_safe_json_value(item) for item in value]
    if pd.isna(value):
        return None
    return str(value)


def _sanitize_top_reasons(value: Any) -> list[dict[str, str]]:
    cleaned: list[dict[str, str]] = []
    for item in _parse_top_reasons_field(value):
        cleaned.append(
            {
                "title": str(item.get("title", "Model signal")).strip() or "Model signal",
                "severity": str(item.get("severity", "low")).strip() or "low",
            }
        )
    return cleaned


def _summary_metrics(row: pd.Series) -> dict[str, float | None]:
    return {key: _safe_float(row.get(key), None) for key in DEFAULT_SUMMARY_KEYS}


def _risk_value(row: pd.Series, raw_col: str) -> float:
    return float(_safe_float(row.get("risk"), _safe_float(row.get("proba_calibrated"), _safe_float(row.get(raw_col), 0.0))) or 0.0)


def _player_row(row: pd.Series, raw_col: str, interpretation: dict[str, Any] | None) -> dict[str, Any]:
    return {
        "steamid": str(row.get("attacker_steamid", "")).strip(),
        "attacker_name": str(row.get("attacker_name", "")).strip() or "Unknown player",
        "proba_cheater_infer": float(_safe_float(row.get(raw_col), 0.0) or 0.0),
        "risk": _risk_value(row, raw_col),
        "confidence": _safe_float(row.get("confidence"), None),
        "ci_low": None,
        "ci_high": None,
        "risk_band": str(row.get("risk_band", "unknown")),
        "features_summary": _summary_metrics(row),
        "top_reasons": _sanitize_top_reasons(row.get("top_reasons")),
        "interpretation": _safe_json_value(interpretation),
    }


def _evidence_table(demo_id: str, steamid: str, filename: str, df: pd.DataFrame, limit: int) -> dict[str, Any]:
    clipped = df.head(max(1, int(limit))).copy()
    rows = [{str(col): _safe_json_value(value) for col, value in record.items()} for record in clipped.to_dict(orient="records")]
    return {
        "demo_id": demo_id,
        "steamid": steamid,
        "filename": filename,
        "columns": [str(col) for col in clipped.columns],
        "rows": rows,
        "row_count": int(len(clipped)),
    }


def _minimal_score_trace(row: pd.Series, raw_col: str) -> dict[str, Any]:
    rt_n = int(float(row.get("rt_n", row.get("n_kills_with_rt", 0)) or 0))
    rounds_played = int(float(row.get("rounds_played", 0) or 0))
    return {
        "steamid": str(row.get("attacker_steamid", "")).strip(),
        "attacker_name": str(row.get("attacker_name", "")).strip() or "Unknown player",
        "raw_proba": float(_safe_float(row.get(raw_col), 0.0) or 0.0),
        "calibrated_proba": _safe_float(row.get("proba_calibrated"), None),
        "risk_display_value": _risk_value(row, raw_col),
        "confidence_value": float(_safe_float(row.get("confidence"), 0.0) or 0.0),
        "gating_rules": {
            "low_evidence_downweight_fired": rt_n < 8,
            "n_kills_with_rt_thresholding_applied": True,
            "n_kills_with_rt_value": rt_n,
        },
        "evidence_counts": {
            "rt_n": rt_n,
            "rounds_played": rounds_played,
            "kills": int(float(row.get("n_kills", 0) or 0)),
        },
        "high_tag_flags": {
            "prefire_pct": bool((_safe_float(row.get("prefire_pct"), 0.0) or 0.0) >= 0.9),
            "thrusmoke_pct": bool((_safe_float(row.get("thrusmoke_pct"), 0.0) or 0.0) >= 0.9),
            "hs_pct": bool((_safe_float(row.get("hs_pct"), 0.0) or 0.0) >= 0.9),
            "long_fast_rt_pct": bool((_safe_float(row.get("long_fast_rt_pct"), 0.0) or 0.0) >= 0.9),
        },
        "feature_row": {key: _safe_float(row.get(key), None) for key in SAFE_TRACE_FEATURE_KEYS},
    }


def _load_debug_score_trace(demo_id: str) -> dict[str, dict[str, Any]]:
    path = PROCESSED_ROOT / "reports" / demo_id / "debug_score_trace.json"
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}

    out: dict[str, dict[str, Any]] = {}
    for item in payload.get("players", []) if isinstance(payload, dict) else []:
        if not isinstance(item, dict):
            continue
        steamid = str(item.get("steamid", "")).strip()
        if not steamid:
            continue
        out[steamid] = {
            "steamid": steamid,
            "attacker_name": str(item.get("attacker_name", "")).strip() or "Unknown player",
            "raw_proba": _safe_float(item.get("raw_proba"), None),
            "calibrated_proba": _safe_float(item.get("calibrated_proba"), None),
            "risk_display_value": _safe_float(item.get("risk_display_value"), None),
            "confidence_value": _safe_float(item.get("confidence_value"), None),
            "gating_rules": _safe_json_value(item.get("gating_rules") or {}),
            "evidence_counts": _safe_json_value(item.get("evidence_counts") or {}),
            "high_tag_flags": _safe_json_value(item.get("high_tag_flags") or {}),
            "why_risk_low_despite_high_tags": _safe_json_value(item.get("why_risk_low_despite_high_tags")),
            "feature_row": {
                key: _safe_float((item.get("feature_row") or {}).get(key), None)
                for key in SAFE_TRACE_FEATURE_KEYS
            },
        }
    return out


def _benchmark_snapshot(path: Path | None) -> dict[str, float] | None:
    if path is None or not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    buckets = payload.get("bucket_summary")
    if not isinstance(buckets, dict):
        return None
    cheater = buckets.get("cheater") or {}
    normal = buckets.get("normal") or {}
    pro = buckets.get("pro") or {}
    return {
        "cheater_top1_hit_rate": float(cheater.get("top1_hit_rate", 0.0) or 0.0),
        "cheater_top3_hit_rate": float(cheater.get("top3_hit_rate", 0.0) or 0.0),
        "legit_median_top1_score": float(normal.get("median_top1_score", 0.0) or 0.0),
        "pro_median_top1_score": float(pro.get("median_top1_score", 0.0) or 0.0),
    }


def main() -> int:
    args = parse_args()
    cfg = default_config(args.mode)
    out_path = (
        Path(args.output)
        if args.output
        else PROCESSED_ROOT / "review_bundles" / f"{args.demo}_{args.mode}.json"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)

    ranked = _read_ranked(cfg.ranked_csv).copy()
    ranked["attacker_steamid"] = _normalize_steamid_series(ranked["attacker_steamid"])
    ranked_demo = ranked[ranked["demo_id"].astype(str) == str(args.demo)].copy()
    if ranked_demo.empty:
        raise ValueError(f"No ranked rows found for demo_id={args.demo} in {cfg.ranked_csv}")

    sort_col = "risk" if "risk" in ranked_demo.columns else cfg.proba_col
    ranked_demo = ranked_demo.sort_values(sort_col, ascending=False).head(max(1, int(args.top))).reset_index(drop=True)

    eng, enc = load_demo_context(cfg, str(args.demo))
    interpretation_map = build_demo_interpretations(ranked_demo, eng, enc)
    debug_trace_map = _load_debug_score_trace(str(args.demo))

    players: list[dict[str, Any]] = []
    reports: dict[str, Any] = {}
    score_traces: dict[str, Any] = {}
    evidence_tables: dict[str, dict[str, Any]] = {}

    for _, row in ranked_demo.iterrows():
        steamid = str(row.get("attacker_steamid", "")).strip()
        if not steamid:
            continue
        interpretation = interpretation_map.get(steamid)
        reasons, evidence = build_reasons(row, eng)
        risk = _risk_value(row, cfg.proba_col)
        confidence = _safe_float(row.get("confidence"), 0.0)

        players.append(_player_row(row, cfg.proba_col, interpretation))
        reports[steamid] = {
            "mode": cfg.mode,
            "demo_id": str(args.demo),
            "player": {
                "attacker_name": str(row.get("attacker_name", "")).strip() or "Unknown player",
                "attacker_steamid": steamid,
            },
            "risk": {
                "score": risk,
                "band": str(row.get("risk_band", "unknown")),
                "raw_probability": _safe_float(row.get(cfg.proba_col), None),
                "calibrated_probability": _safe_float(row.get("proba_calibrated"), None),
            },
            "confidence": {
                "score": confidence,
                "rt_reason_confidence": "low" if int(row.get("rt_n", 0) or 0) < 8 else "normal",
            },
            "uncertainty_ci": None,
            "reasons": _safe_json_value(reasons),
            "signals": _safe_json_value(_build_signals(row)),
            "evidence_files": [name for name, df in evidence.items() if not df.empty],
            "interpretation": _safe_json_value(interpretation),
        }
        score_traces[steamid] = debug_trace_map.get(steamid) or _minimal_score_trace(row, cfg.proba_col)
        evidence_tables[steamid] = {
            filename: _evidence_table(str(args.demo), steamid, filename, df, args.rows_per_evidence)
            for filename, df in evidence.items()
            if not df.empty
        }

    payload = {
        "meta": {
            "schema_version": "nullcs.review-bundle.v1",
            "app_name": "NullCS",
            "source": "local-export",
            "demo_id": str(args.demo),
            "display_name": str(args.demo),
            "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "summary": f"Local review export for {args.demo} containing ranked players, explain reports, score traces, and evidence tables.",
            "benchmark_snapshot": _benchmark_snapshot(Path(args.benchmark_summary)) if args.benchmark_summary else None,
        },
        "players": players,
        "score_traces": score_traces,
        "reports": reports,
        "evidence_tables": evidence_tables,
    }

    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[OK] wrote review bundle: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

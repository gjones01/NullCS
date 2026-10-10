from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.utils.project_paths import PROCESSED_ROOT


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Inspect ranked player output for one demo or player.")
    ap.add_argument("--demo", required=True, help="Demo ID to inspect.")
    ap.add_argument("--steamid", default=None, help="Optional SteamID to inspect.")
    ap.add_argument("--mode", choices=["infer", "oof", "insample"], default="infer", help="Ranked file mode.")
    ap.add_argument("--top", type=int, default=5, help="How many top players to print when --steamid is omitted.")
    return ap.parse_args()


def ranked_path(mode: str) -> Path:
    return PROCESSED_ROOT / "reports" / f"ranked_player_demo_suspicion_{mode}.csv"


def safe_float(v) -> float | None:
    try:
        if pd.isna(v):
            return None
        return float(v)
    except Exception:
        return None


def load_ranked(path: Path, demo_id: str) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Ranked file not found: {path}")
    df = pd.read_csv(path)
    out = df[df["demo_id"].astype(str) == str(demo_id)].copy()
    if out.empty:
        raise ValueError(f"No rows found for demo_id={demo_id} in {path}")
    sort_col = "risk" if "risk" in out.columns else ("proba_calibrated" if "proba_calibrated" in out.columns else "proba_cheater_infer")
    return out.sort_values(sort_col, ascending=False).reset_index(drop=True)


def row_payload(row: pd.Series, rank: int) -> dict[str, object]:
    top_reasons = row.get("top_reasons")
    if isinstance(top_reasons, str) and top_reasons.strip():
        try:
            top_reasons = json.loads(top_reasons)
        except Exception:
            top_reasons = []
    elif not isinstance(top_reasons, list):
        top_reasons = []

    return {
        "rank": rank,
        "attacker_name": str(row.get("attacker_name", "")),
        "attacker_steamid": str(row.get("attacker_steamid", "")).strip(),
        "risk": safe_float(row.get("risk")),
        "risk_band": str(row.get("risk_band", "")),
        "confidence": safe_float(row.get("confidence")),
        "raw_probability": safe_float(row.get("proba_cheater_infer", row.get("proba_raw_oof", row.get("proba_cheater_insample")))),
        "calibrated_probability": safe_float(row.get("proba_calibrated")),
        "summary_metrics": {
            "rt_median": safe_float(row.get("rt_median")),
            "prefire_rate": safe_float(row.get("prefire_rate")),
            "headshot_rate": safe_float(row.get("headshot_rate")),
            "thrusmoke_kill_rate": safe_float(row.get("thrusmoke_kill_rate")),
            "long_range_fast_rt_rate_4": safe_float(row.get("long_range_fast_rt_rate_4")),
            "enc_aim_error_min_median": safe_float(row.get("enc_aim_error_min_median")),
            "enc_aim_acquire_median": safe_float(row.get("enc_aim_acquire_median")),
            "enc_ang_vel_median": safe_float(row.get("enc_ang_vel_median")),
        },
        "top_reasons": top_reasons,
    }


def main() -> int:
    args = parse_args()
    df = load_ranked(ranked_path(args.mode), args.demo)

    if args.steamid:
        sid = str(args.steamid).strip()
        match = df[df["attacker_steamid"].astype(str).str.strip() == sid].copy()
        if match.empty:
            raise ValueError(f"SteamID {sid} not found in demo {args.demo}")
        row = match.iloc[0]
        print(json.dumps(row_payload(row, int(match.index[0]) + 1), indent=2))
        return 0

    top_n = max(1, int(args.top))
    payload = {
        "demo_id": str(args.demo),
        "mode": str(args.mode),
        "player_count": int(len(df)),
        "top_players": [row_payload(row, idx) for idx, (_, row) in enumerate(df.head(top_n).iterrows(), start=1)],
    }
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

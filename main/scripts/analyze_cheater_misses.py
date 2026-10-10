from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
from xgboost import DMatrix, XGBClassifier


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.utils.demo_labels import load_cheater_map
from src.utils.project_paths import DEMOS_ROOT, MODELS_ROOT, PROCESSED_ROOT, REPORTS_ROOT
from src.utils.training_mode import model_artifact_paths


CHEATER_CSV = PROCESSED_ROOT / "CheaterSteamIDs.csv"


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Analyze cheater benchmark misses by comparing the top-ranked player against the labeled cheater row.")
    ap.add_argument("--benchmark-prefix", default="BENCH", help="Benchmark report/demo prefix to inspect, e.g. BENCH or PRUNE2.")
    ap.add_argument("--model-artifact", default=None, help="Optional model artifact filename. Defaults to current CS2CD artifact.")
    ap.add_argument("--top-deltas", type=int, default=12, help="How many contribution deltas to show per miss.")
    ap.add_argument("--top-summary", type=int, default=20, help="How many aggregate feature deltas to summarize.")
    return ap.parse_args()


def _default_model_artifact() -> str:
    return model_artifact_paths(MODELS_ROOT, "cs2cd")["model"].name


def _source_stem_from_demo_id(demo_id: str, prefix: str) -> str:
    stem = str(demo_id)
    expect = f"{prefix.upper()}_CHEATER_"
    if stem.upper().startswith(expect):
        return stem[len(expect) :]
    return stem


def _cheater_key_for_stem(stem: str) -> str:
    if stem.lower().startswith("demo"):
        return f"CDemo{stem[4:]}"
    return stem


def _load_feature_list(model_artifact_name: str) -> list[str]:
    if model_artifact_name.endswith(".json"):
        stem = model_artifact_name[:-5]
    else:
        stem = model_artifact_name
    feats_path = MODELS_ROOT / f"{stem}_features.txt"
    if not feats_path.exists():
        raise FileNotFoundError(f"Missing feature list: {feats_path}")
    return [line.strip() for line in feats_path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _load_model(model_artifact_name: str) -> XGBClassifier:
    model_path = MODELS_ROOT / model_artifact_name
    if not model_path.exists():
        raise FileNotFoundError(f"Missing model artifact: {model_path}")
    model = XGBClassifier()
    model.load_model(str(model_path))
    return model


def _ranked_sort_column(df: pd.DataFrame) -> str:
    for col in ("risk", "proba_calibrated", "proba_cheater_infer"):
        if col in df.columns:
            return col
    raise ValueError("Could not find a score column in ranked inference CSV.")


def _iter_benchmark_demo_ids(prefix: str) -> list[str]:
    pattern = f"{prefix.upper()}_CHEATER_*"
    ids = sorted(
        [p.name for p in REPORTS_ROOT.glob(pattern) if p.is_dir()],
        key=lambda x: (
            int(re.search(r"(\d+)$", x).group(1)) if re.search(r"(\d+)$", x) else 10**9,
            x.lower(),
        ),
    )
    if not ids:
        raise FileNotFoundError(f"No benchmark report directories found for prefix {prefix!r}.")
    return ids


def _contrib_frame(model: XGBClassifier, features: pd.DataFrame, feature_names: list[str]) -> pd.DataFrame:
    matrix = DMatrix(features[feature_names], feature_names=feature_names)
    contribs = model.get_booster().predict(matrix, pred_contribs=True)
    cols = feature_names + ["bias"]
    return pd.DataFrame(contribs, columns=cols, index=features.index)


def main() -> int:
    args = parse_args()
    prefix = str(args.benchmark_prefix).strip().upper()
    model_artifact_name = str(args.model_artifact or _default_model_artifact()).strip()

    cheater_map = load_cheater_map(CHEATER_CSV)
    feature_names = _load_feature_list(model_artifact_name)
    model = _load_model(model_artifact_name)

    miss_rows: list[dict[str, object]] = []
    aggregate_rows: list[dict[str, object]] = []

    for demo_id in _iter_benchmark_demo_ids(prefix):
        ranked_path = REPORTS_ROOT / demo_id / "ranked_players_infer.csv"
        features_path = DEMOS_ROOT / demo_id / "player_features_infer.parquet"
        if not ranked_path.exists() or not features_path.exists():
            continue

        ranked = pd.read_csv(ranked_path, dtype={"attacker_steamid": str})
        score_col = _ranked_sort_column(ranked)
        ranked["attacker_steamid"] = ranked["attacker_steamid"].astype(str).str.strip()
        ranked = ranked.sort_values(score_col, ascending=False).reset_index(drop=True)
        ranked["rank"] = ranked.index + 1

        source_stem = _source_stem_from_demo_id(demo_id, prefix)
        cheater_ids = sorted(cheater_map.get(_cheater_key_for_stem(source_stem), set()))
        if not cheater_ids:
            continue

        cheater_rows = ranked[ranked["attacker_steamid"].isin(cheater_ids)].copy()
        if cheater_rows.empty:
            continue
        cheater_best = cheater_rows.sort_values("rank", ascending=True).iloc[0]
        if int(cheater_best["rank"]) <= 1:
            continue

        top_row = ranked.iloc[0]
        all_features = pd.read_parquet(features_path)
        all_features["attacker_steamid"] = all_features["attacker_steamid"].astype(str).str.strip()
        all_features = all_features.set_index("attacker_steamid", drop=False)
        compare_ids = [str(top_row["attacker_steamid"]), str(cheater_best["attacker_steamid"])]
        if any(sid not in all_features.index for sid in compare_ids):
            continue

        compare = all_features.loc[compare_ids].copy()
        contribs = _contrib_frame(model, compare, feature_names)
        top_sid = str(top_row["attacker_steamid"])
        cheater_sid = str(cheater_best["attacker_steamid"])
        delta = contribs.loc[top_sid, feature_names] - contribs.loc[cheater_sid, feature_names]
        value_delta = compare.loc[top_sid, feature_names] - compare.loc[cheater_sid, feature_names]
        delta_df = pd.DataFrame(
            {
                "feature": feature_names,
                "contrib_delta_top_minus_cheater": delta.values,
                "value_delta_top_minus_cheater": value_delta.values,
                "top_value": compare.loc[top_sid, feature_names].values,
                "cheater_value": compare.loc[cheater_sid, feature_names].values,
            }
        ).sort_values("contrib_delta_top_minus_cheater", ascending=False)

        top_helping = delta_df.head(args.top_deltas).to_dict(orient="records")
        cheater_helping = delta_df.tail(args.top_deltas).sort_values("contrib_delta_top_minus_cheater", ascending=True).to_dict(orient="records")

        miss_rows.append(
            {
                "demo_id": demo_id,
                "source_demo": source_stem,
                "top_name": str(top_row.get("attacker_name", "")),
                "top_steamid": top_sid,
                "top_score": float(top_row[score_col]),
                "cheater_name": str(cheater_best.get("attacker_name", "")),
                "cheater_steamid": cheater_sid,
                "cheater_rank": int(cheater_best["rank"]),
                "cheater_score": float(cheater_best[score_col]),
                "score_gap": float(top_row[score_col] - cheater_best[score_col]),
                "top_helping_features": top_helping,
                "cheater_helping_features": cheater_helping,
            }
        )

        aggregate_rows.extend(
            {
                "demo_id": demo_id,
                "feature": row["feature"],
                "contrib_delta_top_minus_cheater": float(row["contrib_delta_top_minus_cheater"]),
                "abs_contrib_delta": abs(float(row["contrib_delta_top_minus_cheater"])),
                "value_delta_top_minus_cheater": float(row["value_delta_top_minus_cheater"]),
            }
            for row in delta_df.to_dict(orient="records")
        )

    if not miss_rows:
        raise RuntimeError("No cheater misses found for the requested benchmark prefix.")

    agg_df = pd.DataFrame(aggregate_rows)
    summary = (
        agg_df.groupby("feature", as_index=False)
        .agg(
            demos=("demo_id", "nunique"),
            mean_contrib_delta=("contrib_delta_top_minus_cheater", "mean"),
            median_contrib_delta=("contrib_delta_top_minus_cheater", "median"),
            mean_abs_contrib_delta=("abs_contrib_delta", "mean"),
            mean_value_delta=("value_delta_top_minus_cheater", "mean"),
        )
        .sort_values(["mean_contrib_delta", "mean_abs_contrib_delta"], ascending=[False, False])
        .reset_index(drop=True)
    )

    out_dir = REPORTS_ROOT / f"miss_analysis_{prefix.lower()}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    out_dir.mkdir(parents=True, exist_ok=True)

    miss_json = out_dir / "cheater_miss_details.json"
    miss_json.write_text(json.dumps(miss_rows, indent=2), encoding="utf-8")

    summary_csv = out_dir / "feature_delta_summary.csv"
    summary.to_csv(summary_csv, index=False)

    top_summary = summary.head(args.top_summary)
    payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "benchmark_prefix": prefix,
        "model_artifact": model_artifact_name,
        "miss_count": len(miss_rows),
        "mean_cheater_rank_across_misses": float(pd.DataFrame(miss_rows)["cheater_rank"].mean()),
        "mean_score_gap_across_misses": float(pd.DataFrame(miss_rows)["score_gap"].mean()),
        "top_features_helping_wrong_player": top_summary.to_dict(orient="records"),
        "detail_json": str(miss_json),
        "summary_csv": str(summary_csv),
    }
    summary_json = out_dir / "miss_analysis_summary.json"
    summary_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print(f"[OK] wrote {miss_json}")
    print(f"[OK] wrote {summary_csv}")
    print(f"[OK] wrote {summary_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

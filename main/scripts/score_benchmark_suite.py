from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.utils.demo_labels import load_cheater_map
from src.utils.project_paths import CHEATER_DEMOS_ROOT, LEGIT_NORMAL_RENAMED_ROOT, LEGIT_PRO_RENAMED_ROOT, PROCESSED_ROOT, REPORTS_ROOT


CHEATER_CSV = PROCESSED_ROOT / "CheaterSteamIDs.csv"


def _safe_print(text: str) -> None:
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode("ascii", errors="replace").decode("ascii"))


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Run a benchmark suite over local raw demo folders using the live inference pipeline.")
    ap.add_argument("--normal-count", type=int, default=5, help="Number of NormalRenamed demos to score.")
    ap.add_argument("--pro-count", type=int, default=5, help="Number of ProsRenamed demos to score.")
    ap.add_argument("--cheater-count", type=int, default=5, help="Number of CheaterDemos demos to score.")
    ap.add_argument("--device", default="cpu", choices=["cpu", "cuda"], help="Device passed through to inference where applicable.")
    ap.add_argument("--model-artifact", default=None, help="Optional specific XGBoost model artifact.")
    ap.add_argument("--shuffle", action="store_true", help="Shuffle candidate demo lists before selecting counts.")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--demo-prefix", default="BENCH", help="Prefix used for generated benchmark demo IDs.")
    return ap.parse_args()


def _stable_sort_key(path: Path) -> tuple[int, str]:
    stem = path.stem
    digits = "".join(ch for ch in stem if ch.isdigit())
    return (int(digits) if digits else 10**9, stem.lower())


def _select_files(root: Path, count: int, shuffle: bool, seed: int) -> list[Path]:
    files = sorted(root.glob("*.dem"), key=_stable_sort_key)
    if shuffle:
        import random

        rng = random.Random(seed)
        rng.shuffle(files)
    return files[: max(0, count)]


def _benchmark_demo_id(prefix: str, bucket: str, stem: str) -> str:
    safe = "".join(ch if ch.isalnum() else "_" for ch in stem)
    return f"{prefix}_{bucket}_{safe}"


def _cheater_key_for_demo(path: Path) -> str:
    stem = path.stem
    if stem.lower().startswith("demo"):
        suffix = stem[4:]
        return f"CDemo{suffix}"
    return stem


def _run_infer(dem_path: Path, demo_id: str, model_artifact: str | None) -> tuple[Path, pd.DataFrame]:
    cmd = [
        sys.executable,
        str(PROJECT_ROOT / "scripts" / "run_infer_pipeline.py"),
        "--dem_path",
        str(dem_path),
        "--demo_id",
        demo_id,
        "--out_dir",
        str(PROCESSED_ROOT),
    ]
    if model_artifact:
        cmd.extend(["--model-artifact", model_artifact])
        _safe_print(f"[RUN] {' '.join(cmd)}")
    res = subprocess.run(cmd, text=True, capture_output=True)
    if res.stdout:
        _safe_print(res.stdout)
    if res.stderr:
        _safe_print(res.stderr)
    if res.returncode != 0:
        raise RuntimeError(f"Inference failed for {dem_path.name} with exit code {res.returncode}")
    ranked_path = REPORTS_ROOT / demo_id / "ranked_players_infer.csv"
    if not ranked_path.exists():
        raise FileNotFoundError(f"Missing ranked inference CSV for {demo_id}: {ranked_path}")
    ranked = pd.read_csv(ranked_path)
    ranked["attacker_steamid"] = ranked["attacker_steamid"].astype(str).str.strip()
    return ranked_path, ranked


def _summarize_demo(bucket: str, source_path: Path, ranked_path: Path, ranked: pd.DataFrame, cheater_ids: set[str] | None) -> dict[str, object]:
    out = ranked.copy()
    if "risk" in out.columns:
        sort_col = "risk"
    elif "proba_calibrated" in out.columns:
        sort_col = "proba_calibrated"
    else:
        sort_col = "proba_cheater_infer"
    out = out.sort_values(sort_col, ascending=False).reset_index(drop=True)
    out["rank"] = out.index + 1

    top1 = out.iloc[0] if not out.empty else None
    top3_mean = float(out[sort_col].head(3).mean()) if not out.empty else 0.0
    summary: dict[str, object] = {
        "bucket": bucket,
        "source_demo": str(source_path),
        "ranked_csv": str(ranked_path),
        "demo_id": str(out["demo_id"].iloc[0]) if not out.empty and "demo_id" in out.columns else source_path.stem,
        "n_players": int(len(out)),
        "score_column": sort_col,
        "top1_name": str(top1.get("attacker_name", "")) if top1 is not None else "",
        "top1_steamid": str(top1.get("attacker_steamid", "")) if top1 is not None else "",
        "top1_score": float(top1.get(sort_col, 0.0)) if top1 is not None else 0.0,
        "top3_mean_score": top3_mean,
        "max_score": float(out[sort_col].max()) if not out.empty else 0.0,
        "players_over_0_20": int((out[sort_col] >= 0.20).sum()) if not out.empty else 0,
        "players_over_0_50": int((out[sort_col] >= 0.50).sum()) if not out.empty else 0,
        "top5_names": out["attacker_name"].head(5).tolist() if "attacker_name" in out.columns else [],
    }

    if bucket == "cheater":
        known = sorted({str(x).strip() for x in (cheater_ids or set()) if str(x).strip()})
        cheater_rows = out[out["attacker_steamid"].isin(known)].copy()
        summary["known_cheater_ids"] = known
        summary["known_cheater_count_in_map"] = len(known)
        summary["known_cheater_found_count"] = int(len(cheater_rows))
        summary["known_cheater_rank_best"] = int(cheater_rows["rank"].min()) if not cheater_rows.empty else None
        summary["known_cheater_top3_hit"] = bool((cheater_rows["rank"] <= 3).any()) if not cheater_rows.empty else False
        summary["known_cheater_top1_hit"] = bool((cheater_rows["rank"] == 1).any()) if not cheater_rows.empty else False
        summary["known_cheater_scores"] = cheater_rows[["attacker_name", "attacker_steamid", "rank", sort_col]].to_dict(orient="records")
    else:
        summary["known_cheater_ids"] = []
        summary["known_cheater_count_in_map"] = 0
        summary["known_cheater_found_count"] = 0
        summary["known_cheater_rank_best"] = None
        summary["known_cheater_top3_hit"] = False
        summary["known_cheater_top1_hit"] = False
        summary["known_cheater_scores"] = []

    return summary


def _aggregate_suite(summaries: list[dict[str, object]]) -> dict[str, object]:
    out: dict[str, object] = {"buckets": {}}
    for bucket in sorted({str(x["bucket"]) for x in summaries}):
        rows = [x for x in summaries if x["bucket"] == bucket]
        if not rows:
            continue
        df = pd.DataFrame(rows)
        bucket_summary: dict[str, object] = {
            "demos": int(len(df)),
            "median_top1_score": float(df["top1_score"].median()),
            "mean_top1_score": float(df["top1_score"].mean()),
            "median_top3_mean_score": float(df["top3_mean_score"].median()),
            "mean_players_over_0_20": float(df["players_over_0_20"].mean()),
            "mean_players_over_0_50": float(df["players_over_0_50"].mean()),
        }
        if bucket == "cheater":
            valid = df["known_cheater_rank_best"].dropna()
            bucket_summary.update(
                {
                    "top1_hit_rate": float(df["known_cheater_top1_hit"].mean()),
                    "top3_hit_rate": float(df["known_cheater_top3_hit"].mean()),
                    "median_best_cheater_rank": float(valid.median()) if not valid.empty else None,
                    "mean_best_cheater_rank": float(valid.mean()) if not valid.empty else None,
                }
            )
        else:
            bucket_summary.update(
                {
                    "any_demo_top1_over_0_50_rate": float((df["top1_score"] >= 0.50).mean()),
                    "any_demo_top1_over_0_20_rate": float((df["top1_score"] >= 0.20).mean()),
                }
            )
        out["buckets"][bucket] = bucket_summary
    return out


def main() -> int:
    args = parse_args()
    cheater_map = load_cheater_map(CHEATER_CSV)

    selections: list[tuple[str, Path]] = []
    selections.extend([("normal", p) for p in _select_files(LEGIT_NORMAL_RENAMED_ROOT, args.normal_count, args.shuffle, args.seed)])
    selections.extend([("pro", p) for p in _select_files(LEGIT_PRO_RENAMED_ROOT, args.pro_count, args.shuffle, args.seed + 1)])
    selections.extend([("cheater", p) for p in _select_files(CHEATER_DEMOS_ROOT, args.cheater_count, args.shuffle, args.seed + 2)])
    if not selections:
        raise RuntimeError("No benchmark demos selected.")

    run_ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = REPORTS_ROOT / f"benchmark_suite_{run_ts}"
    out_dir.mkdir(parents=True, exist_ok=True)

    summaries: list[dict[str, object]] = []
    for bucket, dem_path in selections:
        demo_id = _benchmark_demo_id(str(args.demo_prefix).strip().upper(), bucket.upper(), dem_path.stem)
        ranked_path, ranked = _run_infer(dem_path, demo_id, args.model_artifact)
        cheater_ids = None
        if bucket == "cheater":
            cheater_ids = cheater_map.get(_cheater_key_for_demo(dem_path), set())
        summary = _summarize_demo(bucket, dem_path, ranked_path, ranked, cheater_ids)
        summaries.append(summary)
        _safe_print(
            f"[BENCH] {bucket} {dem_path.name}: top1={summary['top1_name']} "
            f"score={summary['top1_score']:.4f} "
            f"best_cheater_rank={summary['known_cheater_rank_best']}"
        )

    summary_df = pd.DataFrame(summaries).sort_values(["bucket", "source_demo"]).reset_index(drop=True)
    summary_csv = out_dir / "benchmark_demo_summary.csv"
    summary_df.to_csv(summary_csv, index=False)

    suite_summary = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "model_artifact": args.model_artifact,
        "selected_counts": {
            "normal": args.normal_count,
            "pro": args.pro_count,
            "cheater": args.cheater_count,
        },
        "notes": {
            "pro": "ProsRenamed demos are a stress-test slice, not held-out, because they were added to training.",
            "normal": "NormalRenamed demos are the cleanest held-out legit benchmark slice.",
            "cheater": "CheaterDemos use CheaterSteamIDs.csv for per-player rank checks.",
        },
        "bucket_summary": _aggregate_suite(summaries)["buckets"],
        "demo_summary_csv": str(summary_csv),
    }
    summary_json = out_dir / "benchmark_suite_summary.json"
    summary_json.write_text(json.dumps(suite_summary, indent=2), encoding="utf-8")

    _safe_print(f"[OK] wrote {summary_csv}")
    _safe_print(f"[OK] wrote {summary_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
import sys

import pandas as pd
from sklearn.model_selection import GroupKFold, GridSearchCV, RandomizedSearchCV
from xgboost import XGBClassifier


PROJECT_ROOT = Path(__file__).resolve().parents[1]  # .../main
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.utils.project_paths import PROCESSED_ROOT
from src.utils.scoring import ensure_no_forbidden_features
from src.utils.training_mode import (
    model_artifact_paths_for_stem,
    model_artifact_paths,
    player_features_path,
    player_features_summary_path,
    resolve_train_data_mode,
)


MODELS_ROOT = PROCESSED_ROOT / "models"
MODELS_ROOT.mkdir(parents=True, exist_ok=True)

RANDOM_STATE = 42
N_SPLITS = 5


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Train grouped-CV XGBoost model for a selected training data mode.")
    ap.add_argument(
        "--train-data",
        default=None,
        help="Training data mode: local, cs2cd, or merged. Default resolves from env or merged.",
    )
    ap.add_argument("--search-jobs", type=int, default=1, help="GridSearchCV parallel jobs. Use 1 on Windows if loky fails.")
    ap.add_argument("--xgb-jobs", type=int, default=4, help="XGBoost internal parallel jobs.")
    ap.add_argument("--device", default="cpu", choices=["cpu", "cuda"], help="XGBoost device for model fitting.")
    ap.add_argument("--search-kind", default="random", choices=["random", "grid"], help="Hyperparameter search strategy.")
    ap.add_argument("--random-iters", type=int, default=72, help="RandomizedSearchCV iterations when --search-kind=random.")
    ap.add_argument("--artifact-stem", default=None, help="Optional output artifact stem. Defaults to the mode stem.")
    ap.add_argument(
        "--exclude-features",
        default="",
        help="Comma-separated feature names to exclude from training.",
    )
    ap.add_argument(
        "--upweight-positive-demos",
        default="",
        help="Comma-separated demo_id values whose positive rows should receive extra sample weight.",
    )
    ap.add_argument(
        "--positive-demo-weight",
        type=float,
        default=1.0,
        help="Multiplier applied to positive rows from --upweight-positive-demos.",
    )
    ap.add_argument(
        "--feature-list-path",
        default=None,
        help="Optional path to a newline-delimited feature list. When provided, training is locked to exactly these features.",
    )
    ap.add_argument(
        "--fixed-params-json",
        default=None,
        help="Optional JSON object of XGBoost params. When provided, skip hyperparameter search and fit a single candidate.",
    )
    return ap.parse_args()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def current_commit_hash() -> str | None:
    try:
        res = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True)
        return res.stdout.strip() or None
    except Exception:
        return None


def build_sample_weights(df: pd.DataFrame, demo_ids: list[str], positive_demo_weight: float) -> tuple[pd.Series, dict[str, int]]:
    weights = pd.Series(1.0, index=df.index, dtype=float)
    normalized = {str(x).strip() for x in demo_ids if str(x).strip()}
    if not normalized or float(positive_demo_weight) == 1.0:
        return weights, {"weighted_positive_rows": 0, "weighted_demos_found": 0}
    mask = df["demo_id"].astype(str).isin(normalized) & (df["label"].astype(int) == 1)
    weights.loc[mask] = float(positive_demo_weight)
    stats = {
        "weighted_positive_rows": int(mask.sum()),
        "weighted_demos_found": int(df.loc[df["demo_id"].astype(str).isin(normalized), "demo_id"].nunique()),
    }
    return weights, stats


def main():
    args = parse_args()
    train_mode = resolve_train_data_mode(args.train_data)
    data_path = player_features_path(PROCESSED_ROOT, train_mode)
    summary_path = player_features_summary_path(PROCESSED_ROOT, train_mode)
    artifact_stem = str(args.artifact_stem or "").strip()
    artifact_paths = model_artifact_paths_for_stem(MODELS_ROOT, artifact_stem) if artifact_stem else model_artifact_paths(MODELS_ROOT, train_mode)

    if not data_path.exists():
        raise FileNotFoundError(f"Training table not found for mode={train_mode}: {data_path}")

    df = pd.read_parquet(data_path)

    df = df[df["label"].notna()].copy()
    df["label"] = df["label"].astype(int)
    before_n_players_rows = len(df)
    before_n_players_demos = df["demo_id"].nunique()
    if "n_players" in df.columns:
        df = df[df["n_players"] >= 8].copy()
        print(
            f"[INFO] n_players>=8 filter: rows {before_n_players_rows}->{len(df)} "
            f"demos {before_n_players_demos}->{df['demo_id'].nunique()}"
        )

    groups = df["demo_id"].values
    exclude = {"label", "demo_id", "map_name", "attacker_name", "attacker_steamid", "dataset_source"}
    if args.feature_list_path:
        feature_cols = [line.strip() for line in Path(args.feature_list_path).read_text(encoding="utf-8").splitlines() if line.strip()]
        missing = [c for c in feature_cols if c not in df.columns]
        if missing:
            raise KeyError(f"Requested feature list has columns missing from training table: {missing[:20]}")
        print(f"[INFO] locked feature list from {args.feature_list_path} count={len(feature_cols)}")
    else:
        feature_cols = [c for c in df.columns if c not in exclude and pd.api.types.is_numeric_dtype(df[c])]
    excluded_features = [x.strip() for x in str(args.exclude_features or "").split(",") if x.strip()]
    if excluded_features:
        feature_cols = [c for c in feature_cols if c not in set(excluded_features)]
        print(f"[INFO] excluded features={excluded_features}")
    ensure_no_forbidden_features(feature_cols, "training feature list")

    X = df[feature_cols].fillna(0.0)
    y = df["label"].values

    n_neg = int((y == 0).sum())
    n_pos = int((y == 1).sum())
    scale_pos_weight = n_neg / max(1, n_pos)
    upweight_positive_demos = [x.strip() for x in str(args.upweight_positive_demos or "").split(",") if x.strip()]
    sample_weights, weight_stats = build_sample_weights(df, upweight_positive_demos, float(args.positive_demo_weight))
    print(f"[INFO] train_mode={train_mode} rows={len(df)} neg={n_neg} pos={n_pos} scale_pos_weight={scale_pos_weight:.3f}")
    print(f"[INFO] demos={df['demo_id'].nunique()} features={len(feature_cols)}")
    if upweight_positive_demos and float(args.positive_demo_weight) != 1.0:
        print(
            f"[INFO] upweight_positive_demos={upweight_positive_demos} positive_demo_weight={float(args.positive_demo_weight):.3f} "
            f"weighted_positive_rows={weight_stats['weighted_positive_rows']} weighted_demos_found={weight_stats['weighted_demos_found']}"
        )

    base = XGBClassifier(
        objective="binary:logistic",
        eval_metric="logloss",
        tree_method="hist",
        device=str(args.device),
        random_state=RANDOM_STATE,
        n_jobs=int(args.xgb_jobs),
        scale_pos_weight=scale_pos_weight,
    )

    param_grid = {
        "n_estimators": [400, 800, 1200],
        "max_depth": [3, 4],
        "learning_rate": [0.03, 0.05, 0.08],
        "subsample": [0.8, 1.0],
        "colsample_bytree": [0.8, 1.0],
        "min_child_weight": [3, 8],
        "reg_lambda": [1.0, 5.0],
        "gamma": [0.0],
        "scale_pos_weight": [scale_pos_weight],
        "reg_alpha": [0.0],
    }

    fixed_params = None
    search = None
    if args.fixed_params_json:
        fixed_params = json.loads(str(args.fixed_params_json))
        if not isinstance(fixed_params, dict) or not fixed_params:
            raise ValueError("--fixed-params-json must decode to a non-empty JSON object.")
        best_params = {str(k): v for k, v in fixed_params.items()}
        print("\n[RESULT] Fixed candidate params:")
        for k, v in best_params.items():
            print(f"  {k}: {v}")
        best_model = XGBClassifier(
            objective="binary:logistic",
            eval_metric="logloss",
            tree_method="hist",
            device=str(args.device),
            random_state=RANDOM_STATE,
            n_jobs=int(args.xgb_jobs),
            scale_pos_weight=scale_pos_weight,
            **best_params,
        )
        best_model.fit(X, y, sample_weight=sample_weights.values)
        best_score = None
    else:
        cv = GroupKFold(n_splits=N_SPLITS)
        common_search_kwargs = dict(
            estimator=base,
            scoring="average_precision",
            cv=cv.split(X, y, groups=groups),
            verbose=2,
            n_jobs=int(args.search_jobs),
            return_train_score=True,
        )
        if args.search_kind == "grid":
            search = GridSearchCV(
                param_grid=param_grid,
                **common_search_kwargs,
            )
        else:
            search = RandomizedSearchCV(
                param_distributions=param_grid,
                n_iter=int(args.random_iters),
                random_state=RANDOM_STATE,
                **common_search_kwargs,
            )
        search.fit(X, y, sample_weight=sample_weights.values)

        print("\n[RESULT] Best PR-AUC (CV):", search.best_score_)
        print("[RESULT] Best params:")
        for k, v in search.best_params_.items():
            print(f"  {k}: {v}")

        best_model = search.best_estimator_
        best_params = dict(search.best_params_)
        best_score = float(search.best_score_)
    best_model.save_model(artifact_paths["model"])

    feature_text = "\n".join(feature_cols)
    artifact_paths["features"].write_text(feature_text, encoding="utf-8")

    if search is not None:
        results = pd.DataFrame(search.cv_results_).sort_values("rank_test_score")
    else:
        results = pd.DataFrame(
            [
                {
                    "mode": "fixed_params",
                    "param_set": json.dumps(best_params, sort_keys=True),
                }
            ]
        )
    results.to_csv(artifact_paths["grid_results"], index=False)

    best_params_payload = {
        "train_data_mode": train_mode,
        "best_score_average_precision": best_score,
        "best_params": best_params,
        "search_kind": "fixed" if fixed_params is not None else args.search_kind,
        "artifact_stem": artifact_stem or None,
        "excluded_features": excluded_features,
        "upweight_positive_demos": upweight_positive_demos,
        "positive_demo_weight": float(args.positive_demo_weight),
        "weight_stats": weight_stats,
        "feature_list_path": str(args.feature_list_path) if args.feature_list_path else None,
    }
    artifact_paths["best_params"].write_text(json.dumps(best_params_payload, indent=2), encoding="utf-8")

    aggregate_summary = {}
    if summary_path.exists():
        aggregate_summary = json.loads(summary_path.read_text(encoding="utf-8"))

    manifest = {
        "train_data_mode": train_mode,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "code_commit_hash": current_commit_hash(),
        "training_script": str(Path(__file__)),
        "data_path": str(data_path),
        "aggregate_summary_path": str(summary_path),
        "artifact_paths": {k: str(v) for k, v in artifact_paths.items()},
        "row_counts": {
            "raw_player_rows_from_table": int(before_n_players_rows),
            "rows_after_n_players_filter": int(len(df)),
            "demos_after_n_players_filter": int(df["demo_id"].nunique()),
        },
        "class_balance_after_n_players_filter": {
            "positive": n_pos,
            "negative": n_neg,
        },
        "filters": {
            "n_players": ">= 8",
            "group_split": "GroupKFold by demo_id",
        },
        "feature_count": len(feature_cols),
        "feature_list_sha256": sha256_text(feature_text),
        "feature_columns": feature_cols,
        "best_score_average_precision": best_score,
        "best_params": best_params,
        "search_kind": "fixed" if fixed_params is not None else args.search_kind,
        "random_iters": int(args.random_iters) if search is not None and args.search_kind == "random" else None,
        "artifact_stem": artifact_stem or None,
        "excluded_features": excluded_features,
        "upweight_positive_demos": upweight_positive_demos,
        "positive_demo_weight": float(args.positive_demo_weight),
        "weight_stats": weight_stats,
        "feature_list_path": str(args.feature_list_path) if args.feature_list_path else None,
        "aggregate_summary": aggregate_summary,
    }
    artifact_paths["training_manifest"].write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(f"\n[OK] saved model: {artifact_paths['model']}")
    print(f"[OK] saved features: {artifact_paths['features']}")
    print(f"[OK] saved results: {artifact_paths['grid_results']}")
    print(f"[OK] saved best params: {artifact_paths['best_params']}")
    print(f"[OK] saved training manifest: {artifact_paths['training_manifest']}")


if __name__ == "__main__":
    main()

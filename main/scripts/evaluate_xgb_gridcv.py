from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, confusion_matrix, roc_auc_score
from sklearn.model_selection import GroupKFold
from xgboost import XGBClassifier


PROJECT_ROOT = Path(__file__).resolve().parents[1]  # .../main
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.utils.scoring import (
    apply_rt_low_evidence_downweight,
    compute_confidence_series,
    ensure_no_forbidden_features,
    load_calibrator,
    maybe_calibrate,
    risk_band_series,
    top_signal_titles,
)
from src.utils.project_paths import PROCESSED_ROOT
from src.utils.training_mode import (
    model_artifact_paths_for_stem,
    model_artifact_paths,
    player_features_path,
    report_artifact_paths,
    report_artifact_paths_for_suffix,
    resolve_train_data_mode,
)


MODELS_ROOT = PROCESSED_ROOT / "models"
REPORTS_ROOT = PROCESSED_ROOT / "reports"
REPORTS_ROOT.mkdir(parents=True, exist_ok=True)

N_SPLITS = 5
RANDOM_STATE = 42
THRESHOLDS = [0.2, 0.3, 0.4, 0.5]
TOPK = [1, 2, 3, 5]

FALLBACK_PARAMS = dict(
    colsample_bytree=0.8,
    gamma=0.0,
    learning_rate=0.03,
    max_depth=4,
    min_child_weight=3,
    n_estimators=400,
    reg_alpha=0.0,
    reg_lambda=5.0,
    subsample=0.8,
)


def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("--train-data", default=None, help="Training data mode: local, cs2cd, or merged.")
    ap.add_argument("--use-saved-model", action="store_true")
    ap.add_argument("--write-oof-parquet", action="store_true")
    ap.add_argument("--ablation", action="store_true", help="Compare kill-only vs encounter+kill feature sets with grouped OOF.")
    ap.add_argument("--xgb-jobs", type=int, default=4, help="XGBoost internal parallel jobs for fold retraining.")
    ap.add_argument("--device", default="cpu", choices=["cpu", "cuda"], help="XGBoost device for fold retraining or saved-model scoring.")
    ap.add_argument("--artifact-stem", default=None, help="Optional artifact stem to evaluate instead of the mode default.")
    ap.add_argument(
        "--upweight-positive-demos",
        default="",
        help="Comma-separated demo_id values whose positive rows should receive extra sample weight during fold retraining.",
    )
    ap.add_argument(
        "--positive-demo-weight",
        type=float,
        default=1.0,
        help="Multiplier applied to positive rows from --upweight-positive-demos during fold retraining.",
    )
    return ap.parse_args()


def _normalize_model_params(params: dict) -> dict:
    int_keys = {"max_depth", "min_child_weight", "n_estimators"}
    out = dict(params)
    out.pop("scale_pos_weight", None)
    for key, value in list(out.items()):
        if key in int_keys:
            out[key] = int(value)
        else:
            out[key] = float(value)
    return out


def load_best_params(best_params_path: Path, grid_results_path: Path) -> dict:
    if best_params_path.exists():
        payload = json.loads(best_params_path.read_text(encoding="utf-8"))
        params = payload.get("best_params", payload)
        if isinstance(params, dict) and params:
            return _normalize_model_params(params)
    if grid_results_path.exists():
        df = pd.read_csv(grid_results_path)
        if not df.empty:
            if "rank_test_score" in df.columns:
                row = df.sort_values("rank_test_score", ascending=True).iloc[0]
            else:
                row = df.sort_values("mean_test_score", ascending=False).iloc[0]
            params = {}
            for col in df.columns:
                if col.startswith("param_") and pd.notna(row[col]):
                    params[col[len("param_") :]] = row[col]
            if params:
                return _normalize_model_params(params)
    return dict(FALLBACK_PARAMS)


def predict_with_retrained_folds(X, y, groups, scale_pos_weight, model_params: dict, xgb_jobs: int, device: str) -> tuple[np.ndarray, np.ndarray]:
    return predict_with_retrained_folds_weighted(X, y, groups, scale_pos_weight, model_params, xgb_jobs, device=device, sample_weight=None)


def predict_with_retrained_folds_weighted(X, y, groups, scale_pos_weight, model_params: dict, xgb_jobs: int, device: str, sample_weight: np.ndarray | None) -> tuple[np.ndarray, np.ndarray]:
    oof = np.zeros(len(y), dtype=float)
    fold_ids = np.full(len(y), -1, dtype=int)
    gkf = GroupKFold(n_splits=N_SPLITS)
    for fold, (tr_idx, te_idx) in enumerate(gkf.split(X, y, groups=groups), start=1):
        model = XGBClassifier(
            objective="binary:logistic",
            eval_metric="logloss",
            tree_method="hist",
            device=str(device),
            random_state=RANDOM_STATE,
            n_jobs=int(xgb_jobs),
            scale_pos_weight=scale_pos_weight,
            **model_params,
        )
        fit_kwargs = {}
        if sample_weight is not None:
            fit_kwargs["sample_weight"] = sample_weight[tr_idx]
        model.fit(X.iloc[tr_idx], y[tr_idx], **fit_kwargs)
        oof[te_idx] = model.predict_proba(X.iloc[te_idx])[:, 1]
        fold_ids[te_idx] = fold
        print(f"[FOLD {fold}] done")
    return oof, fold_ids


def predict_with_saved_model(X, model_path: Path) -> np.ndarray:
    model = XGBClassifier()
    model.load_model(str(model_path))
    print(f"[INFO] loaded model from: {model_path}")
    return model.predict_proba(X)[:, 1]


def expected_calibration_error(y_true: np.ndarray, p: np.ndarray, bins: int = 12) -> float:
    edges = np.linspace(0.0, 1.0, bins + 1)
    total = len(y_true)
    acc = 0.0
    for i in range(bins):
        lo = edges[i]
        hi = edges[i + 1]
        mask = (p >= lo) & (p <= hi if i == bins - 1 else p < hi)
        if not mask.any():
            continue
        bin_conf = float(p[mask].mean())
        bin_acc = float(y_true[mask].mean())
        acc += (mask.sum() / total) * abs(bin_conf - bin_acc)
    return float(acc)


def update_training_report(eval_summary_path: Path, train_mode: str) -> None:
    models_root = eval_summary_path.parent
    summaries = []
    for p in sorted(models_root.glob("xgb_player_level_*_eval_summary.json")):
        payload = json.loads(p.read_text(encoding="utf-8"))
        summaries.append(payload)
    if not summaries:
        return

    lines = [
        "# Training Report",
        "",
        "This report summarizes evaluation runs that exist on disk for the current training modes.",
        "",
        "| Mode | Rows | Pos | Neg | ROC-AUC | PR-AUC | Top1 | Top3 | FP@0.50 non-cheater demos | ECE raw | ECE calibrated |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for summary in summaries:
        lines.append(
            "| {mode} | {rows} | {pos} | {neg} | {roc:.4f} | {pr:.4f} | {top1:.4f} | {top3:.4f} | {fp} | {ece_raw:.4f} | {ece_cal:.4f} |".format(
                mode=summary["train_data_mode"],
                rows=summary["rows"],
                pos=summary["positive"],
                neg=summary["negative"],
                roc=summary["roc_auc"],
                pr=summary["pr_auc"],
                top1=summary["cdemo_top1_rate"],
                top3=summary["cdemo_top3_rate"],
                fp=summary["false_positive_non_cheater_demos_at_0_50"],
                ece_raw=summary["ece_raw"],
                ece_cal=summary["ece_calibrated"],
            )
        )
    lines.extend(
        [
            "",
            f"Latest updated mode: `{train_mode}`",
            "",
            "Source files:",
        ]
    )
    for summary in summaries:
        lines.append(f"- `{summary['summary_path']}`")
    (models_root / "TRAINING_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def infer_numeric_feature_cols(df: pd.DataFrame) -> list[str]:
    exclude = {"label", "demo_id", "map_name", "attacker_name", "attacker_steamid", "dataset_source"}
    cols = [c for c in df.columns if c not in exclude and pd.api.types.is_numeric_dtype(df[c])]
    ensure_no_forbidden_features(cols, "dynamic feature inference")
    return cols


def unique_preserve_order(cols: list[str]) -> list[str]:
    return list(dict.fromkeys(cols))


def build_sample_weights(df: pd.DataFrame, demo_ids: list[str], positive_demo_weight: float) -> tuple[np.ndarray | None, dict[str, int]]:
    normalized = {str(x).strip() for x in demo_ids if str(x).strip()}
    if not normalized or float(positive_demo_weight) == 1.0:
        return None, {"weighted_positive_rows": 0, "weighted_demos_found": 0}
    weights = np.ones(len(df), dtype=float)
    mask = df["demo_id"].astype(str).isin(normalized) & (df["label"].astype(int) == 1)
    weights[mask.to_numpy()] = float(positive_demo_weight)
    stats = {
        "weighted_positive_rows": int(mask.sum()),
        "weighted_demos_found": int(df.loc[df["demo_id"].astype(str).isin(normalized), "demo_id"].nunique()),
    }
    return weights, stats


def build_demo_level_summary(out: pd.DataFrame) -> dict[str, float | int]:
    demo_rows = []
    for demo_id, group in out.groupby("demo_id"):
        probs = np.sort(group["risk"].values)[::-1]
        labels_sorted = group.sort_values("risk", ascending=False)["label"].values
        demo_rows.append(
            {
                "demo_id": demo_id,
                "demo_label_any_cheater": int(group["label"].max()),
                "max_proba": float(probs[0]) if len(probs) else 0.0,
                "top1_has_cheater": int(labels_sorted[0] == 1) if len(labels_sorted) else 0,
                "top3_has_cheater": int((labels_sorted[:3] == 1).any()) if len(labels_sorted) else 0,
            }
        )
    demo_df = pd.DataFrame(demo_rows)
    non_cheater_demos = demo_df[demo_df["demo_label_any_cheater"] == 0].copy()
    positive_demos = demo_df[demo_df["demo_label_any_cheater"] == 1].copy()
    return {
        "false_positive_non_cheater_demos_at_0_50": int((non_cheater_demos["max_proba"] >= 0.50).sum()) if not non_cheater_demos.empty else 0,
        "cdemo_top1_rate": float(positive_demos["top1_has_cheater"].mean()) if not positive_demos.empty else 0.0,
        "cdemo_top3_rate": float(positive_demos["top3_has_cheater"].mean()) if not positive_demos.empty else 0.0,
    }


def run_ablation_eval(
    df: pd.DataFrame,
    y: np.ndarray,
    groups: np.ndarray,
    scale_pos_weight: float,
    model_params: dict,
    xgb_jobs: int,
    device: str,
    train_mode: str,
) -> int:
    base_cols = infer_numeric_feature_cols(df)
    feature_sets = {
        "kill_only": [c for c in base_cols if not str(c).startswith("enc_")],
        "encounter_plus_kill": base_cols,
    }
    results: dict[str, dict[str, float | int | list[str]]] = {}

    for name, feature_cols in feature_sets.items():
        X = df[feature_cols].fillna(0.0).astype(float)
        scores, fold_ids = predict_with_retrained_folds(X, y, groups, scale_pos_weight, model_params, xgb_jobs, device=device)
        out = df[["demo_id", "map_name", "attacker_steamid", "attacker_name", "label"]].copy()
        out["attacker_steamid"] = out["attacker_steamid"].astype(str).str.strip()
        out["proba_raw_oof"] = scores
        out["fold_id"] = fold_ids
        out["confidence"] = compute_confidence_series(df)
        out["risk"] = apply_rt_low_evidence_downweight(out["proba_raw_oof"], df.get("rt_n", pd.Series([0] * len(df))))
        out["risk_band"] = risk_band_series(out["risk"], df.get("rt_n"), df.get("n_kills_with_rt"), out.get("confidence"))

        results[name] = {
            "feature_count": len(feature_cols),
            "feature_columns": feature_cols,
            "pr_auc": float(average_precision_score(y, scores)),
            "roc_auc": float(roc_auc_score(y, scores)),
            "ece_raw": expected_calibration_error(y, np.asarray(scores, dtype=float)),
            **build_demo_level_summary(out),
        }

    base = results.get("kill_only", {})
    combo = results.get("encounter_plus_kill", {})
    deltas = {}
    for metric in ["pr_auc", "roc_auc", "cdemo_top1_rate", "cdemo_top3_rate", "false_positive_non_cheater_demos_at_0_50", "ece_raw"]:
        if metric in base and metric in combo:
            deltas[metric] = float(combo[metric]) - float(base[metric])

    out_path = REPORTS_ROOT / f"feature_ablation_{train_mode}.json"
    payload = {
        "feature_sets": results,
        "delta_encounter_plus_kill_vs_kill_only": deltas,
    }
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    md_lines = [
        "# Feature Ablation",
        "",
        f"Mode: `{train_mode}`",
        "",
        "| Feature Set | Features | PR-AUC | ROC-AUC | Top1 | Top3 | FP@0.50 | ECE |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for name, metrics in results.items():
        md_lines.append(
            "| {name} | {feature_count} | {pr_auc:.4f} | {roc_auc:.4f} | {cdemo_top1_rate:.4f} | {cdemo_top3_rate:.4f} | {false_positive_non_cheater_demos_at_0_50} | {ece_raw:.4f} |".format(
                name=name,
                **metrics,
            )
        )
    if deltas:
        md_lines.extend(
            [
                "",
                "Delta (`encounter_plus_kill` minus `kill_only`):",
            ]
        )
        for metric, value in deltas.items():
            md_lines.append(f"- `{metric}`: {value:+.4f}")
    (REPORTS_ROOT / f"feature_ablation_{train_mode}.md").write_text("\n".join(md_lines) + "\n", encoding="utf-8")
    print(f"[OK] wrote {out_path}")
    for name, payload in results.items():
        print(
            "[ABLATION] {name} features={feature_count} PR-AUC={pr_auc:.4f} ROC-AUC={roc_auc:.4f} "
            "Top1={cdemo_top1_rate:.4f} Top3={cdemo_top3_rate:.4f} FP@0.50={false_positive_non_cheater_demos_at_0_50}".format(
                name=name,
                **payload,
            )
        )
    if deltas:
        print("[ABLATION] deltas vs kill_only:")
        for metric, value in deltas.items():
            print(f"  {metric}: {value:+.4f}")
    return 0


def main():
    args = parse_args()
    train_mode = resolve_train_data_mode(args.train_data)
    data_path = player_features_path(PROCESSED_ROOT, train_mode)
    artifact_stem = str(args.artifact_stem or "").strip()
    artifact_paths = model_artifact_paths_for_stem(MODELS_ROOT, artifact_stem) if artifact_stem else model_artifact_paths(MODELS_ROOT, train_mode)
    report_suffix = f"_{artifact_stem}" if artifact_stem else ("" if train_mode == "merged" else f"_{train_mode}")
    report_paths = report_artifact_paths_for_suffix(REPORTS_ROOT, report_suffix)

    if not data_path.exists():
        raise FileNotFoundError(f"Training table not found for mode={train_mode}: {data_path}")

    df = pd.read_parquet(data_path)
    df = df[df["label"].notna()].copy()
    df["label"] = df["label"].astype(int)
    before_rows = len(df)
    before_demos = df["demo_id"].nunique()
    if "n_players" in df.columns:
        df = df[df["n_players"] >= 8].copy()
        print(f"[INFO] n_players>=8 filter: rows {before_rows}->{len(df)} demos {before_demos}->{df['demo_id'].nunique()}")

    feature_cols = artifact_paths["features"].read_text(encoding="utf-8").strip().splitlines()
    ensure_no_forbidden_features(feature_cols, str(artifact_paths["features"]))
    X = df[feature_cols].fillna(0.0).astype(float)
    y = df["label"].values
    groups = df["demo_id"].values

    n_neg = int((y == 0).sum())
    n_pos = int((y == 1).sum())
    scale_pos_weight = n_neg / max(1, n_pos)
    model_params = load_best_params(artifact_paths["best_params"], artifact_paths["grid_results"])
    upweight_positive_demos = [x.strip() for x in str(args.upweight_positive_demos or "").split(",") if x.strip()]
    sample_weight, weight_stats = build_sample_weights(df, upweight_positive_demos, float(args.positive_demo_weight))
    if upweight_positive_demos and float(args.positive_demo_weight) != 1.0:
        print(
            f"[INFO] upweight_positive_demos={upweight_positive_demos} positive_demo_weight={float(args.positive_demo_weight):.3f} "
            f"weighted_positive_rows={weight_stats['weighted_positive_rows']} weighted_demos_found={weight_stats['weighted_demos_found']}"
        )

    if args.ablation:
        return run_ablation_eval(df, y, groups, scale_pos_weight, model_params, args.xgb_jobs, args.device, train_mode)

    if args.use_saved_model:
        scores = predict_with_saved_model(X, artifact_paths["model"])
        fold_ids = np.full(len(y), -1, dtype=int)
        mode = "insample"
        raw_score_col = "proba_cheater_insample"
    else:
        print("[INFO] Default mode: computing grouped OOF predictions with fold retraining.")
        scores, fold_ids = predict_with_retrained_folds_weighted(
            X,
            y,
            groups,
            scale_pos_weight,
            model_params,
            args.xgb_jobs,
            args.device,
            sample_weight=sample_weight,
        )
        mode = "oof"
        raw_score_col = "proba_raw_oof"

    pr = float(average_precision_score(y, scores))
    roc = float(roc_auc_score(y, scores))
    print(f"\n[{mode.upper()}] PR-AUC={pr:.4f} ROC-AUC={roc:.4f}")

    out_cols = unique_preserve_order(
        ["demo_id", "map_name", "attacker_steamid", "attacker_name", "label", *feature_cols]
    )
    out = df[out_cols].copy()
    out["attacker_steamid"] = out["attacker_steamid"].astype(str).str.strip()
    out[raw_score_col] = scores
    out["fold_id"] = fold_ids
    out["y_true"] = out["label"].astype(int)
    out["confidence"] = compute_confidence_series(out)

    calibrator = load_calibrator(model_path=artifact_paths["model"])
    out["proba_calibrated"] = np.nan
    if calibrator is not None:
        out["proba_calibrated"] = maybe_calibrate(out[raw_score_col], calibrator)
        print("[INFO] applied calibrator.")

    risk_base = out["proba_calibrated"].copy()
    missing = risk_base.isna()
    risk_base.loc[missing] = out.loc[missing, raw_score_col].astype(float)
    out["risk"] = apply_rt_low_evidence_downweight(risk_base, out.get("rt_n", pd.Series([0] * len(out))))
    out["risk_band"] = risk_band_series(out["risk"], out.get("rt_n"), out.get("n_kills_with_rt"), out.get("confidence"))
    out["rt_reason_confidence"] = np.where(out.get("rt_n", pd.Series([0] * len(out))).fillna(0).astype(float) < 8, "low", "normal")
    out["top_reasons"] = out.apply(lambda r: json.dumps(top_signal_titles(r, top_k=3)), axis=1)

    out_sorted = out.sort_values("risk", ascending=False)
    out_sorted.to_csv(report_paths["ranked_player_oof"], index=False)
    print(f"[OK] wrote {report_paths['ranked_player_oof']}")

    oof_cols = unique_preserve_order(
        [
            c
            for c in ["demo_id", "attacker_steamid", "y_true", raw_score_col, "fold_id", "n_kills", "rt_n", "hs_n", "smoke_n", "rounds_played", "map_name", "attacker_name", *feature_cols]
            if c in out.columns
        ]
    )
    oof_rows = out[oof_cols].copy()
    if mode == "oof":
        oof_rows.to_csv(report_paths["player_oof_csv"], index=False)
        print(f"[OK] wrote {report_paths['player_oof_csv']}")
        if args.write_oof_parquet:
            oof_rows.to_parquet(report_paths["player_oof_parquet"], index=False)
            print(f"[OK] wrote {report_paths['player_oof_parquet']}")

    demo_rows = []
    for demo_id, group in out.groupby("demo_id"):
        probs = np.sort(group["risk"].values)[::-1]
        labels_sorted = group.sort_values("risk", ascending=False)["label"].values
        row = {
            "demo_id": demo_id,
            "map_name": group["map_name"].iloc[0],
            "demo_label_any_cheater": int(group["label"].max()),
            "n_players": int(len(group)),
            "max_proba": float(probs[0]) if len(probs) else 0.0,
            "top1_has_cheater": int(labels_sorted[0] == 1) if len(labels_sorted) else 0,
            "top2_has_cheater": int((labels_sorted[:2] == 1).any()) if len(labels_sorted) else 0,
            "top3_has_cheater": int((labels_sorted[:3] == 1).any()) if len(labels_sorted) else 0,
        }
        for k in TOPK:
            row[f"top{k}_mean"] = float(probs[:k].mean()) if len(probs) >= k else (float(probs.mean()) if len(probs) else 0.0)
        demo_rows.append(row)

    demo_df = pd.DataFrame(demo_rows).sort_values("top3_mean", ascending=False)
    demo_df.to_csv(report_paths["ranked_demo_oof"], index=False)
    print(f"[OK] wrote {report_paths['ranked_demo_oof']}")

    misses = []
    for demo_id in [d for d in demo_df["demo_id"].tolist() if str(d).lower().startswith(("cdemo", "cs2cd_with_cheater_present", "cs2cd_with_"))]:
        group = out[out["demo_id"] == demo_id].sort_values("risk", ascending=False).copy()
        if group.empty or int((group["label"] == 1).any()) == 0:
            continue
        top1 = group.iloc[0]
        if int(top1["label"]) == 1:
            continue
        cheater = group[group["label"] == 1].iloc[0]
        misses.append(
            {
                "demo_id": str(demo_id),
                "cheater_steamid": str(cheater["attacker_steamid"]),
                "pred_top1_steamid": str(top1["attacker_steamid"]),
                "pred_top1_risk": float(top1["risk"]),
                "cheater_risk": float(cheater["risk"]),
            }
        )
    misses_df = pd.DataFrame(misses)
    misses_df.to_csv(report_paths["top1_misses"], index=False)
    print(f"[OK] wrote {report_paths['top1_misses']}")

    non_cheater_demos = demo_df[demo_df["demo_label_any_cheater"] == 0].copy()
    false_positive_non_cheater_demos = int((non_cheater_demos["max_proba"] >= 0.50).sum()) if not non_cheater_demos.empty else 0
    positive_demos = demo_df[demo_df["demo_label_any_cheater"] == 1].copy()
    top1_rate = float(positive_demos["top1_has_cheater"].mean()) if not positive_demos.empty else 0.0
    top3_rate = float(positive_demos["top3_has_cheater"].mean()) if not positive_demos.empty else 0.0

    raw_probs = np.asarray(out[raw_score_col].astype(float))
    cal_probs = np.asarray(out["proba_calibrated"].fillna(out[raw_score_col]).astype(float))
    summary = {
        "train_data_mode": train_mode,
        "summary_path": str(artifact_paths["eval_summary"]),
        "rows": int(len(out)),
        "demos": int(out["demo_id"].nunique()),
        "positive": n_pos,
        "negative": n_neg,
        "roc_auc": roc,
        "pr_auc": pr,
        "cdemo_top1_rate": top1_rate,
        "cdemo_top3_rate": top3_rate,
        "false_positive_non_cheater_demos_at_0_50": false_positive_non_cheater_demos,
        "ece_raw": expected_calibration_error(y, raw_probs),
        "ece_calibrated": expected_calibration_error(y, cal_probs),
        "upweight_positive_demos": upweight_positive_demos,
        "positive_demo_weight": float(args.positive_demo_weight),
        "weight_stats": weight_stats,
        "thresholds": {},
    }
    for thr in THRESHOLDS:
        pred = (scores >= thr).astype(int)
        tn, fp, fn, tp = confusion_matrix(y, pred).ravel()
        summary["thresholds"][str(thr)] = {
            "tp": int(tp),
            "fp": int(fp),
            "fn": int(fn),
            "tn": int(tn),
            "precision": float(tp / max(1, tp + fp)),
            "recall": float(tp / max(1, tp + fn)),
        }
        print(
            f"  thr={thr:.2f} TP={tp} FP={fp} FN={fn} TN={tn} "
            f"prec={summary['thresholds'][str(thr)]['precision']:.3f} rec={summary['thresholds'][str(thr)]['recall']:.3f}"
        )

    artifact_paths["eval_summary"].write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"[OK] wrote {artifact_paths['eval_summary']}")
    update_training_report(artifact_paths["eval_summary"], train_mode)
    print(f"[OK] wrote {MODELS_ROOT / 'TRAINING_REPORT.md'}")


if __name__ == "__main__":
    main()

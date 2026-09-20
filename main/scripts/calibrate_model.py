from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd
from joblib import dump
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, log_loss, roc_auc_score


PROJECT_ROOT = Path(__file__).resolve().parents[1]  # .../main
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.utils.project_paths import PROCESSED_ROOT
from src.utils.training_mode import model_artifact_paths, report_artifact_paths, resolve_train_data_mode


MODELS_ROOT = PROCESSED_ROOT / "models"
REPORTS_ROOT = PROCESSED_ROOT / "reports"


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Fit probability calibrator from OOF-only predictions.")
    ap.add_argument("--train-data", default=None, help="Training data mode: local, cs2cd, or merged.")
    ap.add_argument("--bins", type=int, default=12)
    ap.add_argument("--min-isotonic-positives", type=int, default=25)
    return ap.parse_args()


def load_oof(csv_path: Path, parquet_path: Path) -> pd.DataFrame:
    if parquet_path.exists():
        return pd.read_parquet(parquet_path)
    if csv_path.exists():
        return pd.read_csv(csv_path)
    raise FileNotFoundError(f"Missing OOF predictions file. Expected {parquet_path} or {csv_path}.")


def binned_curve(y: np.ndarray, p_raw: np.ndarray, p_cal: np.ndarray, bins: int) -> pd.DataFrame:
    q = pd.qcut(p_raw, q=bins, duplicates="drop")
    df = pd.DataFrame({"y_true": y, "proba_raw": p_raw, "proba_cal": p_cal, "bin": q})
    rows = []
    for idx, (bin_name, chunk) in enumerate(df.groupby("bin", dropna=True), start=1):
        rows.append(
            {
                "bin_id": idx,
                "bin": str(bin_name),
                "n": int(len(chunk)),
                "mean_pred_raw": float(chunk["proba_raw"].mean()),
                "mean_pred_calibrated": float(chunk["proba_cal"].mean()),
                "empirical_pos_rate": float(chunk["y_true"].mean()),
            }
        )
    return pd.DataFrame(rows)


def main() -> int:
    args = parse_args()
    train_mode = resolve_train_data_mode(args.train_data)
    artifact_paths = model_artifact_paths(MODELS_ROOT, train_mode)
    report_paths = report_artifact_paths(REPORTS_ROOT, train_mode)

    df = load_oof(report_paths["player_oof_csv"], report_paths["player_oof_parquet"])
    raw_col = "proba_raw_oof" if "proba_raw_oof" in df.columns else "proba_cheater_oof"
    if "y_true" not in df.columns or raw_col not in df.columns:
        raise ValueError(f"OOF file must contain y_true and {raw_col} columns.")

    y = df["y_true"].astype(int).to_numpy()
    p_raw = np.clip(df[raw_col].astype(float).to_numpy(), 1e-6, 1.0 - 1e-6)

    n = len(y)
    n_pos = int((y == 1).sum())
    n_neg = int((y == 0).sum())
    if n == 0 or n_pos == 0 or n_neg == 0:
        raise ValueError("Need both positive and negative OOF rows for calibration.")

    method = "isotonic"
    if n_pos < int(args.min_isotonic_positives) or n < 200:
        method = "sigmoid"

    if method == "isotonic":
        model = IsotonicRegression(out_of_bounds="clip")
        model.fit(p_raw, y)
        payload = {"method": "isotonic", "model": model}
        p_cal = np.clip(model.predict(p_raw), 0.0, 1.0)
    else:
        model = LogisticRegression(solver="lbfgs", max_iter=2000)
        model.fit(p_raw.reshape(-1, 1), y)
        payload = {"method": "sigmoid", "model": model}
        p_cal = np.clip(model.predict_proba(p_raw.reshape(-1, 1))[:, 1], 0.0, 1.0)

    dump(payload, artifact_paths["calibrator"])
    print(f"[OK] wrote calibrator: {artifact_paths['calibrator']}")

    summary = {
        "train_data_mode": train_mode,
        "n_rows": int(n),
        "n_pos": int(n_pos),
        "n_neg": int(n_neg),
        "method": method,
        "raw_brier": float(brier_score_loss(y, p_raw)),
        "calibrated_brier": float(brier_score_loss(y, p_cal)),
        "raw_logloss": float(log_loss(y, p_raw)),
        "calibrated_logloss": float(log_loss(y, p_cal)),
        "raw_roc_auc": float(roc_auc_score(y, p_raw)),
        "calibrated_roc_auc": float(roc_auc_score(y, p_cal)),
        "raw_pr_auc": float(average_precision_score(y, p_raw)),
        "calibrated_pr_auc": float(average_precision_score(y, p_cal)),
    }
    artifact_paths["calibration_summary"].write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"[OK] wrote summary: {artifact_paths['calibration_summary']}")

    curve = binned_curve(y, p_raw, p_cal, bins=max(4, int(args.bins)))
    curve.to_csv(artifact_paths["calibration_curve"], index=False)
    print(f"[OK] wrote calibration curve: {artifact_paths['calibration_curve']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

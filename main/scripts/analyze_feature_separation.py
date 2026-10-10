from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.utils.project_paths import PROCESSED_ROOT, REPORTS_ROOT
from src.utils.scoring import ensure_no_forbidden_features
from src.utils.training_mode import player_features_path, resolve_train_data_mode


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Analyze feature separation for cheater vs non-cheater labels.")
    ap.add_argument("--train-data", default=None, help="Training data mode: local, cs2cd, or merged.")
    ap.add_argument("--top-k", type=int, default=40, help="Rows to include in markdown summary.")
    return ap.parse_args()


def safe_auc(y: pd.Series, x: pd.Series) -> float:
    mask = y.notna() & x.notna()
    if int(mask.sum()) < 8:
        return np.nan
    if int(y[mask].nunique()) < 2:
        return np.nan
    try:
        auc = float(roc_auc_score(y[mask].astype(int), x[mask].astype(float)))
        return max(auc, 1.0 - auc)
    except Exception:
        return np.nan


def cohens_d(pos: pd.Series, neg: pd.Series) -> float:
    p = pd.to_numeric(pos, errors="coerce").dropna()
    n = pd.to_numeric(neg, errors="coerce").dropna()
    if len(p) < 2 or len(n) < 2:
        return np.nan
    p_var = float(p.var(ddof=1))
    n_var = float(n.var(ddof=1))
    pooled = ((len(p) - 1) * p_var + (len(n) - 1) * n_var) / max(1, len(p) + len(n) - 2)
    if pooled <= 0:
        return np.nan
    return float((p.mean() - n.mean()) / np.sqrt(pooled))


def analyze_feature(df: pd.DataFrame, feature: str) -> dict[str, object]:
    s = pd.to_numeric(df[feature], errors="coerce")
    y = df["label"].astype(int)
    pos = s[y == 1]
    neg = s[y == 0]
    valid = s.notna()
    pos_missing = float((~valid & (y == 1)).sum() / max(1, (y == 1).sum()))
    neg_missing = float((~valid & (y == 0)).sum() / max(1, (y == 0).sum()))
    return {
        "feature": feature,
        "count_non_null": int(valid.sum()),
        "auc_abs": safe_auc(y, s),
        "cohens_d": cohens_d(pos, neg),
        "mean_pos": float(pos.mean()) if pos.notna().any() else np.nan,
        "mean_neg": float(neg.mean()) if neg.notna().any() else np.nan,
        "median_pos": float(pos.median()) if pos.notna().any() else np.nan,
        "median_neg": float(neg.median()) if neg.notna().any() else np.nan,
        "median_gap": float(pos.median() - neg.median()) if pos.notna().any() and neg.notna().any() else np.nan,
        "p90_pos": float(pos.quantile(0.9)) if pos.notna().any() else np.nan,
        "p90_neg": float(neg.quantile(0.9)) if neg.notna().any() else np.nan,
        "missing_rate_pos": pos_missing,
        "missing_rate_neg": neg_missing,
        "missing_gap": float(pos_missing - neg_missing),
    }


def main() -> int:
    args = parse_args()
    train_mode = resolve_train_data_mode(args.train_data)
    data_path = player_features_path(PROCESSED_ROOT, train_mode)
    if not data_path.exists():
        raise FileNotFoundError(f"Training table not found for mode={train_mode}: {data_path}")

    df = pd.read_parquet(data_path)
    df = df[df["label"].notna()].copy()
    df["label"] = df["label"].astype(int)
    if "n_players" in df.columns:
        before = len(df)
        df = df[df["n_players"] >= 8].copy()
        print(f"[INFO] n_players>=8 filter: {before}->{len(df)} rows")

    exclude = {"label", "demo_id", "map_name", "attacker_name", "attacker_steamid", "dataset_source"}
    feature_cols = [c for c in df.columns if c not in exclude and pd.api.types.is_numeric_dtype(df[c])]
    ensure_no_forbidden_features(feature_cols, "feature separation analysis")

    rows = [analyze_feature(df, c) for c in feature_cols]
    out = pd.DataFrame(rows)
    out["abs_cohens_d"] = out["cohens_d"].abs()
    out = out.sort_values(["auc_abs", "abs_cohens_d", "count_non_null"], ascending=[False, False, False]).reset_index(drop=True)

    REPORTS_ROOT.mkdir(parents=True, exist_ok=True)
    csv_path = REPORTS_ROOT / f"feature_separation_{train_mode}.csv"
    md_path = REPORTS_ROOT / f"feature_separation_{train_mode}.md"
    json_path = REPORTS_ROOT / f"feature_separation_{train_mode}.json"
    out.to_csv(csv_path, index=False)

    top = out.head(int(args.top_k)).copy()
    lines = [
        "# Feature Separation",
        "",
        f"Mode: `{train_mode}`",
        "",
        f"Rows: {len(df)}  Demos: {df['demo_id'].nunique()}  Positives: {(df['label'] == 1).sum()}  Negatives: {(df['label'] == 0).sum()}",
        "",
        "| Feature | AUC* | |d| | Median+ | Median- | Missing+ | Missing- |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for _, row in top.iterrows():
        lines.append(
            "| {feature} | {auc_abs:.4f} | {abs_cohens_d:.4f} | {median_pos:.4f} | {median_neg:.4f} | {missing_rate_pos:.3f} | {missing_rate_neg:.3f} |".format(
                **row.to_dict()
            )
        )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    summary = {
        "train_data_mode": train_mode,
        "data_path": str(data_path),
        "rows": int(len(df)),
        "demos": int(df["demo_id"].nunique()),
        "positives": int((df["label"] == 1).sum()),
        "negatives": int((df["label"] == 0).sum()),
        "top_features_by_auc_abs": top.head(20)["feature"].tolist(),
        "artifacts": {
            "csv": str(csv_path),
            "md": str(md_path),
        },
    }
    json_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(f"[OK] wrote {csv_path}")
    print(f"[OK] wrote {md_path}")
    print(f"[OK] wrote {json_path}")
    print("[TOP]")
    print(top[["feature", "auc_abs", "abs_cohens_d", "median_pos", "median_neg"]].head(15).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

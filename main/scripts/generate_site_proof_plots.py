from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(r"C:\NullCS")
REPORTS_ROOT = ROOT / "main" / "data" / "processed" / "reports"
MODELS_ROOT = ROOT / "main" / "data" / "processed" / "models"
OUT_ROOT = ROOT / "docs" / "assets" / "site_proof"


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def latest_benchmark_suite() -> Path:
    suites = sorted(
        [p for p in REPORTS_ROOT.glob("benchmark_suite_*") if (p / "benchmark_suite_summary.json").exists()],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not suites:
        raise FileNotFoundError("No benchmark suite with summary json found.")
    return suites[0]


def apply_style() -> None:
    plt.rcParams.update(
        {
            "figure.facecolor": "#050910",
            "axes.facecolor": "#0a1019",
            "savefig.facecolor": "#050910",
            "axes.edgecolor": (1, 1, 1, 0.12),
            "axes.labelcolor": "#c8d2df",
            "xtick.color": "#a9b6c8",
            "ytick.color": "#a9b6c8",
            "text.color": "#eef4ff",
            "font.size": 11,
            "axes.titleweight": "bold",
            "axes.grid": True,
            "grid.color": (1, 1, 1, 0.06),
            "grid.linewidth": 0.8,
        }
    )


def save(fig: plt.Figure, filename: str) -> None:
    path = OUT_ROOT / filename
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    print(f"[OK] wrote {path}")


def plot_benchmark_distribution(df: pd.DataFrame) -> None:
    order = ["cheater", "normal", "pro"]
    labels = ["Suspicious", "Normal legit", "Pro stress-test"]
    colors = ["#d58e4d", "#6fbf80", "#6d8ccf"]
    data = [df.loc[df["bucket"] == bucket, "top1_score"].astype(float).values for bucket in order]

    fig, ax = plt.subplots(figsize=(11.5, 6.5))
    bp = ax.boxplot(
        data,
        patch_artist=True,
        widths=0.55,
        medianprops={"color": "#f5f8ff", "linewidth": 2},
        whiskerprops={"color": "#95a3b7"},
        capprops={"color": "#95a3b7"},
        boxprops={"edgecolor": "#95a3b7"},
    )
    for patch, color in zip(bp["boxes"], colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.65)

    for idx, arr in enumerate(data, start=1):
        x = np.random.default_rng(10 + idx).normal(idx, 0.045, size=len(arr))
        ax.scatter(x, arr, s=18, color="#f5f8ff", alpha=0.14, linewidths=0)

    ax.set_xticks(range(1, 4), labels)
    ax.set_ylabel("Top-ranked score")
    ax.set_title("Benchmark slice separation")
    ax.text(
        0.01,
        1.03,
        "Best single website plot: suspicious demos separate clearly while normal legit and pro slices stay quiet.",
        transform=ax.transAxes,
        color="#9cb0c8",
        fontsize=10,
    )
    save(fig, "benchmark_top1_distribution.png")


def plot_retrieval_and_quietness(summary: dict) -> None:
    cheater = summary["bucket_summary"]["cheater"]
    normal = summary["bucket_summary"]["normal"]
    pro = summary["bucket_summary"]["pro"]

    fig, axes = plt.subplots(1, 2, figsize=(13.5, 5.8))

    ax = axes[0]
    retrieval = [cheater["top1_hit_rate"], cheater["top3_hit_rate"]]
    bars = ax.bar(["Top-1", "Top-3"], retrieval, color=["#d58e4d", "#77c989"], width=0.58)
    for bar, v in zip(bars, retrieval):
        ax.text(bar.get_x() + bar.get_width() / 2, v + 0.02, f"{v:.1%}", ha="center", va="bottom", fontsize=12)
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("Share of suspicious demos surfaced")
    ax.set_title("Retrieval on suspicious benchmark slice")

    ax = axes[1]
    thresholds = ["Any top-1 >= 0.20", "Any top-1 >= 0.50"]
    normal_vals = [normal["any_demo_top1_over_0_20_rate"], normal["any_demo_top1_over_0_50_rate"]]
    pro_vals = [pro["any_demo_top1_over_0_20_rate"], pro["any_demo_top1_over_0_50_rate"]]
    x = np.arange(len(thresholds))
    width = 0.32
    ax.bar(x - width / 2, normal_vals, width=width, color="#6fbf80", label="Normal legit")
    ax.bar(x + width / 2, pro_vals, width=width, color="#6d8ccf", label="Pro stress-test")
    ax.set_xticks(x, thresholds)
    ax.set_ylim(0, 0.12)
    ax.set_ylabel("Share of demos")
    ax.set_title("Quietness on legit and pro slices")
    ax.legend(frameon=False)

    save(fig, "retrieval_and_quietness.png")


def plot_cheater_rank_cdf(df: pd.DataFrame) -> None:
    cheater = df.loc[df["bucket"] == "cheater", "known_cheater_rank_best"].dropna().astype(float).sort_values().values
    if len(cheater) == 0:
        return
    y = np.arange(1, len(cheater) + 1) / len(cheater)
    fig, ax = plt.subplots(figsize=(10.5, 5.8))
    ax.step(cheater, y, where="post", color="#7ad7f0", linewidth=2.6)
    ax.scatter(cheater, y, color="#d58e4d", s=18)
    ax.set_xlim(1, max(5, int(np.nanmax(cheater)) + 0.5))
    ax.set_ylim(0, 1.02)
    ax.set_xlabel("Best labeled cheater rank in demo")
    ax.set_ylabel("Cumulative share of suspicious demos")
    ax.set_title("How often the known cheater lands near the top")
    ax.text(1.02, 0.92, "Farther left is better", color="#9cb0c8", fontsize=10)
    save(fig, "cheater_rank_cdf.png")


def plot_top1_vs_top3(df: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(9.5, 7))
    palette = {"cheater": "#d58e4d", "normal": "#6fbf80", "pro": "#6d8ccf"}
    names = {"cheater": "Suspicious", "normal": "Normal legit", "pro": "Pro stress-test"}
    for bucket, color in palette.items():
        work = df[df["bucket"] == bucket]
        ax.scatter(
            work["top1_score"].astype(float),
            work["top3_mean_score"].astype(float),
            s=42,
            alpha=0.72,
            color=color,
            label=names[bucket],
        )
    ax.set_xlabel("Top-1 score")
    ax.set_ylabel("Top-3 mean score")
    ax.set_title("Per-demo score surface")
    ax.legend(frameon=False)
    save(fig, "benchmark_top1_vs_top3_scatter.png")


def plot_feature_auc_bars(feat_df: pd.DataFrame) -> None:
    top = feat_df.sort_values("auc_abs", ascending=False).head(12).iloc[::-1]
    fig, ax = plt.subplots(figsize=(10.8, 7.2))
    colors = ["#7ad7f0" if str(name).startswith("enn_") else "#d58e4d" for name in top["feature"]]
    ax.barh(top["feature"], top["auc_abs"], color=colors, alpha=0.85)
    ax.set_xlabel("Single-feature AUC")
    ax.set_xlim(0.5, min(1.0, float(top["auc_abs"].max()) + 0.03))
    ax.set_title("Highest-ROI feature separation")
    ax.text(
        0.01,
        1.03,
        "This is useful on a website because it shows the model is not running on one gimmick metric.",
        transform=ax.transAxes,
        color="#9cb0c8",
        fontsize=10,
    )
    save(fig, "feature_auc_top12.png")


def plot_feature_median_gap(feat_df: pd.DataFrame) -> None:
    top = feat_df.sort_values("median_gap", ascending=False).head(10).iloc[::-1]
    fig, ax = plt.subplots(figsize=(10.8, 7.0))
    ax.barh(top["feature"], top["median_gap"], color="#77c989", alpha=0.82)
    ax.set_xlabel("Positive vs negative median gap")
    ax.set_title("Features with the clearest median split")
    save(fig, "feature_median_gap_top10.png")


def plot_metric_band_comparison(bands: dict) -> None:
    metrics = [
        ("enc_process_abnormality", "Process abnormality"),
        ("enc_precision_under_difficulty", "Precision under difficulty"),
        ("headshot_rate", "Headshot rate"),
        ("thrusmoke_kill_rate", "Through-smoke kill rate"),
    ]
    groups = [("cheater_top1", "Suspicious"), ("normal_top1", "Normal legit"), ("pro_top1", "Pro stress-test")]
    x = np.arange(len(metrics))
    width = 0.22
    colors = ["#d58e4d", "#6fbf80", "#6d8ccf"]

    fig, ax = plt.subplots(figsize=(12.6, 6.4))
    for idx, ((group_key, label), color) in enumerate(zip(groups, colors)):
        vals = [bands[group_key][metric]["median"] for metric, _ in metrics]
        ax.bar(x + (idx - 1) * width, vals, width=width, color=color, alpha=0.88, label=label)

    ax.set_xticks(x, [label for _, label in metrics])
    ax.set_ylabel("Median top-ranked value")
    ax.set_title("Top-ranked player behavior across slices")
    ax.legend(frameon=False)
    save(fig, "slice_metric_band_comparison.png")


def plot_oof_feature_scatter(oof_df: pd.DataFrame) -> None:
    cols = ["enn_score_mean", "enc_process_abnormality", "y_true"]
    work = oof_df[cols].dropna().copy()
    pos = work[work["y_true"] == 1].sample(min(900, int((work["y_true"] == 1).sum())), random_state=7)
    neg = work[work["y_true"] == 0].sample(min(1800, int((work["y_true"] == 0).sum())), random_state=7)

    fig, ax = plt.subplots(figsize=(9.6, 7.2))
    ax.scatter(neg["enn_score_mean"], neg["enc_process_abnormality"], s=16, color="#6fbf80", alpha=0.22, label="Legit / non-cheater")
    ax.scatter(pos["enn_score_mean"], pos["enc_process_abnormality"], s=18, color="#d58e4d", alpha=0.45, label="Suspicious / cheater slice")
    ax.set_xlabel("Encounter NN score mean")
    ax.set_ylabel("Process abnormality")
    ax.set_title("A cleaner deep-behavior scatter")
    ax.legend(frameon=False)
    save(fig, "oof_behavior_scatter.png")


def plot_threshold_tradeoff(eval_summary: dict) -> None:
    thresholds = []
    precision = []
    recall = []
    for key, stats in sorted(eval_summary["thresholds"].items(), key=lambda kv: float(kv[0])):
        thresholds.append(float(key))
        precision.append(float(stats["precision"]))
        recall.append(float(stats["recall"]))

    fig, ax = plt.subplots(figsize=(9.8, 5.8))
    ax.plot(thresholds, precision, marker="o", linewidth=2.3, color="#7ad7f0", label="Precision")
    ax.plot(thresholds, recall, marker="o", linewidth=2.3, color="#d58e4d", label="Recall")
    ax.set_xticks(thresholds)
    ax.set_ylim(0.55, 1.0)
    ax.set_xlabel("Decision threshold")
    ax.set_ylabel("Score")
    ax.set_title("Threshold tradeoff snapshot")
    ax.legend(frameon=False)
    save(fig, "threshold_tradeoff.png")


def plot_calibration_summary(cal_summary: dict, eval_summary: dict) -> None:
    labels = ["Brier", "Log loss", "ECE", "ROC-AUC", "PR-AUC"]
    raw = [
        cal_summary["raw_brier"],
        cal_summary["raw_logloss"],
        eval_summary["ece_raw"],
        cal_summary["raw_roc_auc"],
        cal_summary["raw_pr_auc"],
    ]
    cal = [
        cal_summary["calibrated_brier"],
        cal_summary["calibrated_logloss"],
        eval_summary["ece_calibrated"],
        cal_summary["calibrated_roc_auc"],
        cal_summary["calibrated_pr_auc"],
    ]

    x = np.arange(len(labels))
    width = 0.34
    fig, ax = plt.subplots(figsize=(10.8, 5.8))
    ax.bar(x - width / 2, raw, width=width, color="#6d8ccf", alpha=0.82, label="Raw")
    ax.bar(x + width / 2, cal, width=width, color="#77c989", alpha=0.82, label="Calibrated")
    ax.set_xticks(x, labels)
    ax.set_title("Calibration and model-quality snapshot")
    ax.legend(frameon=False)
    save(fig, "calibration_quality_snapshot.png")


def main() -> None:
    ensure_dir(OUT_ROOT)
    apply_style()

    suite_dir = latest_benchmark_suite()
    summary = json.loads((suite_dir / "benchmark_suite_summary.json").read_text(encoding="utf-8"))
    benchmark_df = pd.read_csv(suite_dir / "benchmark_demo_summary.csv")
    feat_df = pd.read_csv(REPORTS_ROOT / "feature_separation_cs2cd.csv")
    bands = json.loads((REPORTS_ROOT / "player_metric_bands_summary.json").read_text(encoding="utf-8"))
    eval_summary = json.loads((MODELS_ROOT / "xgb_player_level_cs2cd_eval_summary.json").read_text(encoding="utf-8"))
    cal_summary = json.loads((MODELS_ROOT / "xgb_player_level_cs2cd_calibration_summary.json").read_text(encoding="utf-8"))
    oof_df = pd.read_csv(REPORTS_ROOT / "player_oof_predictions_cs2cd.csv")

    print(f"[INFO] benchmark suite: {suite_dir}")
    print(f"[INFO] writing plot pack to: {OUT_ROOT}")

    plot_benchmark_distribution(benchmark_df)
    plot_retrieval_and_quietness(summary)
    plot_cheater_rank_cdf(benchmark_df)
    plot_top1_vs_top3(benchmark_df)
    plot_feature_auc_bars(feat_df)
    plot_feature_median_gap(feat_df)
    plot_metric_band_comparison(bands)
    plot_oof_feature_scatter(oof_df)
    plot_threshold_tradeoff(eval_summary)
    plot_calibration_summary(cal_summary, eval_summary)

    print("[DONE] site proof plot pack generated")


if __name__ == "__main__":
    main()

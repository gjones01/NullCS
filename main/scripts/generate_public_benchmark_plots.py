from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "docs" / "assets" / "plots"
REPORTS_ROOT = ROOT / "main" / "data" / "processed" / "reports"


def latest_benchmark_summary() -> dict:
    suites = sorted(
        [path for path in REPORTS_ROOT.glob("benchmark_suite_*") if (path / "benchmark_suite_summary.json").is_file()],
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not suites:
        raise FileNotFoundError("No benchmark suite summary found.")
    summary_path = suites[0] / "benchmark_suite_summary.json"
    print(f"[INFO] using benchmark summary: {summary_path}")
    return json.loads(summary_path.read_text(encoding="utf-8"))


def _style() -> None:
    plt.rcParams.update(
        {
            "figure.facecolor": "#0b0f14",
            "axes.facecolor": "#111821",
            "axes.edgecolor": "#263241",
            "axes.labelcolor": "#e8eef7",
            "xtick.color": "#cfd8e3",
            "ytick.color": "#cfd8e3",
            "text.color": "#f5f7fb",
            "axes.titlecolor": "#f5f7fb",
            "font.size": 12,
            "axes.titleweight": "bold",
            "axes.grid": True,
            "grid.color": "#22303f",
            "grid.alpha": 0.45,
            "grid.linestyle": "-",
            "grid.linewidth": 0.8,
            "savefig.facecolor": "#0b0f14",
            "savefig.edgecolor": "#0b0f14",
        }
    )


def _ensure_out() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)


def build_benchmark_slice_plot(summary: dict) -> None:
    bucket_summary = summary["bucket_summary"]
    categories = ["Suspicious\nbenchmark", "Normal\nlegit", "Pro\nstress-test"]
    median = np.array([
        bucket_summary["cheater"]["median_top1_score"],
        bucket_summary["normal"]["median_top1_score"],
        bucket_summary["pro"]["median_top1_score"],
    ])
    mean = np.array([
        bucket_summary["cheater"]["mean_top1_score"],
        bucket_summary["normal"]["mean_top1_score"],
        bucket_summary["pro"]["mean_top1_score"],
    ])
    x = np.arange(len(categories))
    width = 0.28
    colors = {"median": "#91f2a7", "mean": "#8fb7ff"}

    fig = plt.figure(figsize=(11, 8.5), dpi=160)
    gs = fig.add_gridspec(2, 1, height_ratios=[3.5, 1.35], hspace=0.12)
    ax_main = fig.add_subplot(gs[0])
    ax_zoom = fig.add_subplot(gs[1])

    for ax in (ax_main, ax_zoom):
        ax.bar(x - width / 2, median, width=width, color=colors["median"], label="Median top-ranked signal")
        ax.bar(x + width / 2, mean, width=width, color=colors["mean"], label="Mean top-ranked signal")
        ax.set_xticks(x, categories)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.set_axisbelow(True)

    ax_main.set_ylim(0, max(0.08, float(max(median.max(), mean.max())) * 1.28))
    ax_zoom.set_ylim(0, max(0.006, float(max(median[1:].max(), mean[1:].max())) * 1.6))
    ax_main.set_ylabel("Signal")
    ax_zoom.set_ylabel("Signal")

    ax_main.set_title("Benchmark suspicious cases surface while legit play stays quiet", fontsize=20, pad=18)
    fig.text(
        0.5,
        0.91,
        "Public-safe comparison of top-ranked match-relative triage signal across benchmark slices",
        ha="center",
        va="center",
        fontsize=12.5,
        color="#b6c2cf",
    )

    ax_main.legend(
        loc="upper right",
        frameon=False,
        fontsize=10.5,
        labelcolor="#dfe7f1",
    )

    ax_main.annotate(
        "Suspicious slice is intentionally much louder",
        xy=(x[0], median[0]),
        xytext=(0.45, 0.77),
        textcoords="axes fraction",
        arrowprops=dict(arrowstyle="-", color="#7f91a3", lw=1.2),
        fontsize=11,
        color="#cfd8e3",
    )
    ax_zoom.annotate(
        "Legit and pro slices remain compressed near zero",
        xy=(x[1], mean[1]),
        xytext=(0.35, 0.85),
        textcoords="axes fraction",
        arrowprops=dict(arrowstyle="-", color="#7f91a3", lw=1.0),
        fontsize=10.5,
        color="#cfd8e3",
    )

    for idx, val in enumerate(median):
        if val > 0.012:
            ax_main.text(idx - width / 2, val + 0.018, f"{val:.3f}", ha="center", va="bottom", fontsize=11, color="#dff7e5")
        else:
            ax_zoom.text(idx - width / 2, val + 0.00035, f"{val:.4f}", ha="center", va="bottom", fontsize=10, color="#dff7e5")

    for idx, val in enumerate(mean):
        if val > 0.012:
            ax_main.text(idx + width / 2, val + 0.018, f"{val:.3f}", ha="center", va="bottom", fontsize=11, color="#dce7ff")
        else:
            ax_zoom.text(idx + width / 2, val + 0.00035, f"{val:.4f}", ha="center", va="bottom", fontsize=10, color="#dce7ff")

    fig.text(
        0.06,
        0.05,
        "NullCS outputs are match-relative review signals, not verdicts. Lower legit/pro values are desirable because the goal is fewer false positives on strong legitimate players.",
        ha="left",
        va="bottom",
        fontsize=10,
        color="#9fb0c0",
    )
    fig.text(0.94, 0.05, "NULLCS", ha="right", va="bottom", fontsize=10.5, color="#e7edf5", weight="bold")

    fig.savefig(OUT_DIR / "benchmark_slice_signals.png", bbox_inches="tight", pad_inches=0.35)
    plt.close(fig)


def build_retrieval_plot(summary: dict) -> None:
    labels = ["Top-1\nretrieval", "Top-3\nretrieval"]
    cheater = summary["bucket_summary"]["cheater"]
    values = np.array([cheater["top1_hit_rate"], cheater["top3_hit_rate"]])
    colors = ["#f4be74", "#91f2a7"]

    fig, ax = plt.subplots(figsize=(9, 6), dpi=160)
    x = np.arange(len(labels))
    bars = ax.bar(x, values, width=0.42, color=colors)

    ax.set_ylim(0, 1.0)
    ax.set_xticks(x, labels)
    ax.set_ylabel("Share of suspicious matches retrieved")
    ax.set_title("Suspicious benchmark retrieval stays strong at the top of the lobby", fontsize=18, pad=16)
    ax.text(
        0.5,
        1.02,
        "High-level public-safe retrieval summary from the current match-level triage stack",
        transform=ax.transAxes,
        ha="center",
        va="bottom",
        fontsize=11.5,
        color="#b6c2cf",
    )
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.set_axisbelow(True)

    for rect, value in zip(bars, values):
        ax.text(
            rect.get_x() + rect.get_width() / 2,
            value + 0.03,
            f"{int(round(value * 100))}%",
            ha="center",
            va="bottom",
            fontsize=16,
            weight="bold",
            color="#f5f7fb",
        )

    ax.text(
        0.5,
        -0.18,
        "Interpretation: suspicious benchmark players are often surfaced first, and very often within the top three. This supports review prioritization rather than a standalone cheating claim.",
        transform=ax.transAxes,
        ha="center",
        va="top",
        fontsize=10,
        color="#9fb0c0",
        wrap=True,
    )
    fig.text(0.94, 0.05, "NULLCS", ha="right", va="bottom", fontsize=10.5, color="#e7edf5", weight="bold")

    fig.savefig(OUT_DIR / "cheater_retrieval_summary.png", bbox_inches="tight", pad_inches=0.35)
    plt.close(fig)


def main() -> None:
    _ensure_out()
    _style()
    summary = latest_benchmark_summary()
    build_benchmark_slice_plot(summary)
    build_retrieval_plot(summary)


if __name__ == "__main__":
    main()

from __future__ import annotations

import json
import shutil
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch


ROOT = Path(__file__).resolve().parents[2]
DEMOS_ROOT = ROOT / "main" / "data" / "processed" / "demos"
REPORTS_ROOT = ROOT / "main" / "data" / "processed" / "reports"
MODELS_ROOT = ROOT / "main" / "data" / "processed" / "models"
OUT_ROOT = ROOT / "docs" / "assets" / "site_proof"
SITE_OUT_ROOT = ROOT / "main" / "ui" / "site" / "public" / "assets" / "proof-pack"


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


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
    ensure_dir(OUT_ROOT)
    ensure_dir(SITE_OUT_ROOT)
    out_path = OUT_ROOT / filename
    fig.savefig(out_path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    shutil.copyfile(out_path, SITE_OUT_ROOT / filename)
    print(f"[OK] wrote {out_path}")


def load_benchmark_players() -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    wanted = [
        "demo_id",
        "attacker_steamid",
        "attacker_name",
        "enc_input_burst_score",
        "enc_input_stability_score",
        "aim_process_global_score",
        "enc_mouse_delta_mean",
        "enc_mouse_dx_flip_mean",
        "enc_mouse_quiet_mean",
        "enc_ang_jerk_mean",
    ]
    for demo_dir in sorted(DEMOS_ROOT.glob("BENCH_*")):
        if not demo_dir.is_dir():
            continue
        if "CHEATER" in demo_dir.name:
            bucket = "Cheater"
        elif "NORMAL" in demo_dir.name:
            bucket = "Normal"
        elif "PRO" in demo_dir.name:
            bucket = "Pro"
        else:
            continue
        path = demo_dir / "player_features_infer.parquet"
        if not path.exists():
            continue
        frame = pd.read_parquet(path, columns=wanted)
        frame["bucket"] = bucket
        frames.append(frame)
    if not frames:
        raise FileNotFoundError("No BENCH_* player_features_infer.parquet files found.")
    return pd.concat(frames, ignore_index=True)


def load_feature_separation() -> pd.DataFrame:
    path = REPORTS_ROOT / "feature_separation_cs2cd.csv"
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path)


def load_player_metric_bands() -> dict:
    path = REPORTS_ROOT / "player_metric_bands_summary.json"
    if not path.exists():
        raise FileNotFoundError(path)
    return json.loads(path.read_text())


def load_training_scale() -> tuple[dict, dict]:
    encounter_manifest = json.loads((MODELS_ROOT / "encounter_nn_cs2cd_training_manifest.json").read_text())
    xgb_summary = json.loads((MODELS_ROOT / "xgb_player_level_cs2cd_eval_summary.json").read_text())
    return encounter_manifest, xgb_summary


def plot_control_path_boxplots(df: pd.DataFrame) -> None:
    metrics = [
        ("enc_mouse_delta_mean", "Mouse delta mean"),
        ("enc_mouse_dx_flip_mean", "Mouse dx flip rate"),
        ("enc_mouse_quiet_mean", "Quiet-after-acquire rate"),
        ("enc_ang_jerk_mean", "Angular jerk mean"),
    ]
    order = ["Cheater", "Normal", "Pro"]
    colors = {"Cheater": "#d58e4d", "Normal": "#76c28a", "Pro": "#6f88d6"}

    fig, axes = plt.subplots(2, 2, figsize=(12.8, 8.8))
    axes = axes.flatten()
    for ax, (metric, label) in zip(axes, metrics):
        data = [df.loc[df["bucket"] == bucket, metric].dropna().astype(float).values for bucket in order]
        bp = ax.boxplot(
            data,
            patch_artist=True,
            widths=0.58,
            medianprops={"color": "#f5f8ff", "linewidth": 2},
            whiskerprops={"color": "#95a3b7"},
            capprops={"color": "#95a3b7"},
            boxprops={"edgecolor": "#95a3b7"},
        )
        for patch, bucket in zip(bp["boxes"], order):
            patch.set_facecolor(colors[bucket])
            patch.set_alpha(0.68)
        for idx, bucket in enumerate(order, start=1):
            sample = df.loc[df["bucket"] == bucket, metric].dropna().astype(float)
            sample = sample.sample(min(len(sample), 90), random_state=20 + idx)
            x = np.random.default_rng(100 + idx).normal(idx, 0.05, len(sample))
            ax.scatter(x, sample, s=12, color="#f5f8ff", alpha=0.14, linewidths=0)
        ax.set_xticks(range(1, 4), order)
        ax.set_title(label)
        ax.grid(True, axis="y")

    fig.suptitle("Control-path signatures derived from usercmd mouse and crosshair behavior", fontsize=18, y=0.98)
    fig.text(
        0.5,
        0.01,
        "These are player-level aggregates built from encounter windows. They summarize how mouse delta and crosshair behavior differ across cheater, normal, and pro benchmark slices.",
        ha="center",
        color="#9cb0c8",
        fontsize=10,
    )
    save(fig, "control_path_bucket_boxplots.png")


def plot_control_path_scatter(df: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(10.4, 7.4))
    palette = {"Cheater": "#d58e4d", "Normal": "#76c28a", "Pro": "#6f88d6"}
    for bucket, color in palette.items():
        work = df[df["bucket"] == bucket].dropna(subset=["enc_input_burst_score", "enc_input_stability_score"])
        work = work.sample(min(len(work), 140), random_state=42)
        ax.scatter(
            work["enc_input_burst_score"],
            work["enc_input_stability_score"],
            color=color,
            alpha=0.55,
            s=28,
            label=bucket,
        )
    ax.set_xlabel("Input burst score")
    ax.set_ylabel("Input stability score")
    fig.suptitle("Control-path behavior space", fontsize=18, y=0.97)
    ax.legend(frameon=False)
    fig.text(
        0.5,
        0.92,
        "This view compresses usercmd-derived control-path behavior into two axes: burstiness and stability under encounter pressure.",
        ha="center",
        color="#9cb0c8",
        fontsize=10,
    )
    fig.subplots_adjust(top=0.84)
    save(fig, "control_path_score_scatter.png")


def plot_control_path_feature_auc(feat_df: pd.DataFrame) -> None:
    mask = feat_df["feature"].astype(str).str.contains(
        "mouse|input|jerk|aim_error|quiet|burst|stability",
        case=False,
        na=False,
    )
    top = feat_df.loc[mask, ["feature", "auc_abs"]].sort_values("auc_abs", ascending=False).head(12).iloc[::-1]
    fig, ax = plt.subplots(figsize=(10.8, 7.4))
    ax.barh(top["feature"], top["auc_abs"], color="#d58e4d", alpha=0.86)
    ax.set_xlabel("Single-feature AUC")
    ax.set_xlim(0.5, min(1.0, float(top["auc_abs"].max()) + 0.03))
    fig.suptitle("Highest-ROI control-path features", fontsize=18, y=0.97)
    fig.text(
        0.5,
        0.92,
        "These features come from mouse-delta, input-stability, aim-process, and angular-jerk summaries rather than clip-level stats.",
        ha="center",
        color="#9cb0c8",
        fontsize=10,
    )
    fig.subplots_adjust(top=0.88)
    save(fig, "control_path_feature_auc.png")


def plot_top1_control_bands(bands: dict) -> None:
    metrics = [
        ("enc_input_burst_score", "Input burst"),
        ("enc_input_stability_score", "Input stability"),
        ("aim_process_global_score", "Aim process"),
        ("enc_mouse_burst_mean", "Mouse burst"),
    ]
    groups = [("cheater_top1", "Cheater"), ("normal_top1", "Normal"), ("pro_top1", "Pro")]
    colors = ["#d58e4d", "#76c28a", "#6f88d6"]
    x = np.arange(len(metrics))
    width = 0.22

    fig, ax = plt.subplots(figsize=(12.2, 6.4))
    for idx, ((group_key, label), color) in enumerate(zip(groups, colors)):
        vals = [bands[group_key][metric]["median"] for metric, _ in metrics]
        ax.bar(x + (idx - 1) * width, vals, width=width, color=color, alpha=0.88, label=label)

    ax.set_xticks(x, [label for _, label in metrics])
    ax.set_ylabel("Median top-ranked value")
    ax.set_title("Top-ranked control-path profile by benchmark slice")
    ax.legend(frameon=False)
    save(fig, "top1_control_band_comparison.png")


def plot_training_scale(encounter_manifest: dict, xgb_summary: dict) -> None:
    labels = ["Labeled matches", "Encounter rows", "Player rows", "Player features", "CNN channels"]
    values = [
        encounter_manifest["demos"],
        encounter_manifest["rows"],
        xgb_summary["rows"],
        449,
        encounter_manifest["feature_count"],
    ]
    colors = ["#d58e4d", "#c27b54", "#9c89dd", "#76c28a", "#6f88d6"]

    fig, ax = plt.subplots(figsize=(11.2, 6.2))
    bars = ax.bar(labels, values, color=colors, alpha=0.9)
    ax.set_yscale("log")
    ax.set_ylabel("Count / scale (log axis)")
    fig.suptitle("How the current training stack scales", fontsize=18, y=0.97)
    for bar, value in zip(bars, values):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            value * 1.15,
            f"{value:,}",
            ha="center",
            va="bottom",
            fontsize=10,
        )
    fig.text(
        0.5,
        0.92,
        "A single CS2 demo is not one row. It expands into many encounter windows, control-path summaries, and player-level aggregates before the final ranking stage.",
        ha="center",
        color="#9cb0c8",
        fontsize=10,
    )
    fig.subplots_adjust(top=0.88)
    save(fig, "training_data_scale.png")


def plot_pipeline_flow() -> None:
    fig, ax = plt.subplots(figsize=(13.2, 6.8))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 6)
    ax.axis("off")

    boxes = [
        (0.5, 3.8, 1.55, 1.1, "#111722", "CS2 demo", "Raw match file"),
        (2.4, 3.8, 1.75, 1.1, "#111722", "Parser + events", "Kills, shots, damage,\nround and tick structure"),
        (4.55, 3.8, 1.95, 1.1, "#111722", "Encounter builder", "Visibility, aim error,\nmouse delta, jerk"),
        (6.95, 4.45, 2.15, 1.0, "#1a2230", "Encounter CNN", "Temporal control-path\nchannels"),
        (6.95, 3.05, 2.15, 1.0, "#1a2230", "Player aggregation", "449 player-level features"),
        (9.4, 3.75, 1.6, 1.1, "#1c2a1f", "XGBoost ranker", "Contextual player ordering"),
        (6.95, 1.35, 4.05, 0.95, "#2a1813", "Review output", "Ranked players, reasons, benchmark context, evidence"),
    ]

    for x, y, w, h, color, title, body in boxes:
        patch = FancyBboxPatch(
            (x, y),
            w,
            h,
            boxstyle="round,pad=0.03,rounding_size=0.16",
            linewidth=1.1,
            edgecolor=(1, 1, 1, 0.14),
            facecolor=color,
        )
        ax.add_patch(patch)
        ax.text(x + 0.12, y + h - 0.25, title, fontsize=12.5, fontweight="bold", va="top")
        ax.text(x + 0.12, y + 0.2, body, fontsize=10.5, color="#b9c6d7", va="bottom")

    arrows = [
        ((2.05, 4.35), (2.4, 4.35)),
        ((4.15, 4.35), (4.55, 4.35)),
        ((6.5, 4.35), (6.95, 4.95)),
        ((6.5, 4.35), (6.95, 3.55)),
        ((9.1, 4.95), (9.4, 4.35)),
        ((9.1, 3.55), (9.4, 4.15)),
        ((10.2, 3.75), (8.95, 2.3)),
    ]
    for start, end in arrows:
        arrow = FancyArrowPatch(start, end, arrowstyle="-|>", mutation_scale=16, linewidth=1.6, color="#8fb4d9")
        ax.add_patch(arrow)

    ax.text(
        0.02,
        0.98,
        "How the current NullCS stack stays readable",
        transform=ax.transAxes,
        fontsize=18,
        fontweight="bold",
        va="top",
    )
    ax.text(
        0.02,
        0.91,
        "The encounter CNN does not replace the player-level model. Its temporal outputs feed into the broader player aggregate stack, which then drives the final XGBoost ranking.",
        transform=ax.transAxes,
        fontsize=10.5,
        color="#9cb0c8",
        va="top",
    )
    save(fig, "pipeline_review_flow.png")


def main() -> None:
    apply_style()
    benchmark_players = load_benchmark_players()
    feat_df = load_feature_separation()
    bands = load_player_metric_bands()
    encounter_manifest, xgb_summary = load_training_scale()

    plot_control_path_boxplots(benchmark_players)
    plot_control_path_scatter(benchmark_players)
    plot_control_path_feature_auc(feat_df)
    plot_top1_control_bands(bands)
    plot_training_scale(encounter_manifest, xgb_summary)
    plot_pipeline_flow()


if __name__ == "__main__":
    main()

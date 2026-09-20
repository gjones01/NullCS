from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib import patheffects
from matplotlib.collections import LineCollection
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.gridspec import GridSpec


REPORTS_ROOT = Path(r"C:\NullCS\main\data\processed\reports")
DEMOS_ROOT = Path(r"C:\NullCS\main\data\processed\demos")
OUT_ROOT = Path(r"C:\NullCS\docs\assets\trailer_real")


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def apply_dark_axis(ax) -> None:
    ax.set_facecolor("#0a0f18")
    ax.grid(color=(1, 1, 1, 0.07), linewidth=0.8)
    ax.tick_params(colors="#a7b7cc", labelsize=9)
    for spine in ax.spines.values():
        spine.set_color((1, 1, 1, 0.12))


def neon_text(
    ax,
    x,
    y,
    text,
    color="#eaf3ff",
    size=16,
    ha="left",
    va="center",
    **kwargs,
):
    t = ax.text(
        x,
        y,
        text,
        color=color,
        fontsize=size,
        ha=ha,
        va=va,
        family="DejaVu Sans",
        **kwargs,
    )
    t.set_path_effects(
        [
            patheffects.Stroke(linewidth=6, foreground=(0.4, 0.86, 1.0, 0.08)),
            patheffects.Normal(),
        ]
    )
    return t


def save(fig, path: Path) -> None:
    fig.savefig(path, dpi=180, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"[OK] wrote {path}")


def latest_demo_id() -> str:
    report_dirs = [p for p in REPORTS_ROOT.iterdir() if p.is_dir() and (p / "ranked_players_infer.csv").exists()]
    if not report_dirs:
        raise FileNotFoundError(f"No report directories with ranked_players_infer.csv found under {REPORTS_ROOT}")
    report_dirs.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return report_dirs[0].name


def norm_series(values: pd.Series | np.ndarray) -> np.ndarray:
    arr = np.asarray(values, dtype=float)
    if arr.size == 0:
        return arr
    lo = np.nanmin(arr)
    hi = np.nanmax(arr)
    if not np.isfinite(lo) or not np.isfinite(hi) or hi - lo < 1e-9:
        return np.full_like(arr, 0.5, dtype=float)
    return (arr - lo) / (hi - lo)


def load_data(demo_id: str):
    report_dir = REPORTS_ROOT / demo_id
    demo_dir = DEMOS_ROOT / demo_id
    ranked = pd.read_csv(report_dir / "ranked_players_infer.csv")
    players = pd.read_parquet(demo_dir / "player_features_infer.parquet")
    encounters = pd.read_parquet(demo_dir / "encounters.parquet")
    top = ranked.sort_values("risk", ascending=False).iloc[0]
    ranked["attacker_steamid_str"] = ranked["attacker_steamid"].astype(str)
    players["attacker_steamid_str"] = players["attacker_steamid"].astype(str)
    encounters["attacker_steamid_str"] = encounters["attacker_steamid"].astype(str)
    steamid = str(top["attacker_steamid"])
    name = top["attacker_name"]
    top_player = players[players["attacker_steamid_str"] == steamid].iloc[0]
    player_enc = (
        encounters[encounters["attacker_steamid_str"] == steamid]
        .sort_values(["round_num", "start_tick"])
        .reset_index(drop=True)
    )
    return ranked, players, encounters, top, top_player, player_enc, name


def make_real_aim_trace(out_dir: Path, demo_id: str, player_name: str, player_enc: pd.DataFrame) -> None:
    enc = player_enc.head(18).copy()
    if enc.empty:
        return
    x = np.cumsum(enc["snap_velocity_early_max"].fillna(0).to_numpy() * 0.05)
    y = np.cumsum((enc["aim_error_at_first_visible"].fillna(0) - enc["aim_error_min"].fillna(0)).to_numpy() * -0.08)
    x = norm_series(x)
    y = norm_series(y)
    points = np.array([x, y]).T.reshape(-1, 1, 2)
    segments = np.concatenate([points[:-1], points[1:]], axis=1)
    cmap = LinearSegmentedColormap.from_list("nullcs_real_aim", ["#7ee8ff", "#b8f5c2", "#ffb65a", "#ff7d90"])

    fig, ax = plt.subplots(figsize=(11.5, 6.8), facecolor="#050910")
    ax.set_facecolor("#07101a")
    lc = LineCollection(segments, cmap=cmap, norm=plt.Normalize(0, len(enc) - 1))
    lc.set_array(np.arange(len(enc) - 1))
    lc.set_linewidth(3.4)
    ax.add_collection(lc)
    ax.scatter(x, y, c=np.arange(len(enc)), cmap=cmap, s=22, alpha=0.88)
    ax.scatter([x[-1]], [y[-1]], s=240, c="#ffffff", alpha=0.08)
    ax.scatter([x[-1]], [y[-1]], s=56, c="#fefefe", edgecolors="#8be9ff", linewidths=1.6)
    neon_text(ax, 0.02, 0.96, f"REAL AIM TRACE / {player_name}", size=18, va="top")
    neon_text(ax, 0.02, 0.905, f"{demo_id} • encounter path from real snap and collapse metrics", color="#94aac4", size=11, va="top")
    final_lag = enc["acquire_to_shot_lag"].fillna(0).iloc[-1]
    neon_text(ax, x[-1] - 0.02, y[-1] + 0.06, f"lag {final_lag:.0f}t", color="#ffd89c", size=10, ha="right")
    ax.set_xlim(-0.03, 1.03)
    ax.set_ylim(-0.03, 1.03)
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)
    save(fig, out_dir / "real_aim_trace.png")


def make_real_visibility_timeline(out_dir: Path, demo_id: str, player_name: str, player_enc: pd.DataFrame) -> None:
    enc = player_enc.head(24).copy()
    if enc.empty:
        return
    enc["idx"] = np.arange(1, len(enc) + 1)
    vis = enc["visible_ratio"].fillna(0)
    move = norm_series(enc["attacker_speed_mean"].fillna(0) + enc["relative_speed_mean"].fillna(0))
    anticipation = 1.0 - norm_series(enc["time_to_first_shot"].fillna(enc["time_to_first_shot"].median()))

    fig, ax = plt.subplots(figsize=(11.5, 6.4), facecolor="#060a12")
    apply_dark_axis(ax)
    ax.fill_between(enc["idx"], vis, color=(0.45, 0.9, 1.0, 0.08))
    ax.plot(enc["idx"], vis, color="#7ee8ff", linewidth=2.4, label="Visibility ratio")
    ax.plot(enc["idx"], move, color="#b9f7c2", linewidth=2.0, label="Movement pressure")
    ax.plot(enc["idx"], anticipation, color="#ffb55d", linewidth=2.0, label="Pre-shot anticipation")
    hot_idx = int(np.nanargmax(anticipation))
    ax.scatter([enc["idx"].iloc[hot_idx]], [anticipation[hot_idx]], s=90, color="#fff1c1", edgecolors="#ffb55d", linewidths=1.2, zorder=4)
    ax.set_xlim(1, len(enc))
    ax.set_ylim(0, 1.0)
    ax.set_xlabel("Encounter index", color="#b7c6d8")
    ax.set_ylabel("Normalized intensity", color="#b7c6d8")
    ax.legend(loc="upper left", frameon=False, labelcolor="#dce7f5")
    neon_text(ax, 0.015, 1.045, f"REAL VISIBILITY / MOVEMENT CONTEXT • {player_name}", size=18, va="bottom", transform=ax.transAxes)
    neon_text(ax, 0.015, 1.005, f"{demo_id} • derived from actual encounter rows", color="#94aac4", size=11, va="bottom", transform=ax.transAxes)
    save(fig, out_dir / "real_visibility_context_timeline.png")


def make_real_radar(out_dir: Path, demo_id: str, player_name: str, players: pd.DataFrame, top_player: pd.Series) -> None:
    metrics = [
        ("Process", "enc_process_abnormality"),
        ("Occlusion", "enc_low_vis_precision_retention"),
        ("Timing", "enc_acquire_shot_lag_p90"),
        ("Difficulty", "enc_precision_under_difficulty"),
        ("Stability", "enc_input_stability_score"),
        ("NN signal", "enn_score_mean"),
    ]
    vals = []
    labels = []
    for label, col in metrics:
        if col not in players.columns:
            continue
        labels.append(label)
        vals.append(float(pd.Series(players[col]).rank(pct=True).loc[top_player.name]))
    if not vals:
        return
    values = np.array(vals)
    angles = np.linspace(0, 2 * np.pi, len(labels), endpoint=False)
    angles = np.concatenate([angles, [angles[0]]])
    values = np.concatenate([values, [values[0]]])

    fig = plt.figure(figsize=(8.2, 8.2), facecolor="#060a12")
    ax = plt.subplot(111, polar=True)
    ax.set_facecolor("#08101a")
    ax.plot(angles, values, color="#79e7ff", linewidth=2.8)
    ax.fill(angles, values, color=(0.4, 0.92, 1.0, 0.12))
    ax.scatter(angles[:-1], values[:-1], s=55, color="#eefcff", edgecolors="#79e7ff", linewidths=1.2, zorder=3)
    ax.set_theta_offset(np.pi / 2)
    ax.set_theta_direction(-1)
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(labels, color="#dfe9f5", fontsize=11)
    ax.set_yticks([0.2, 0.4, 0.6, 0.8])
    ax.set_yticklabels(["20", "40", "60", "80"], color="#8da3bf", fontsize=9)
    ax.grid(color=(1, 1, 1, 0.08))
    ax.spines["polar"].set_color((1, 1, 1, 0.12))
    fig.text(0.11, 0.93, f"REAL MULTI-LENS RADAR • {player_name}", color="#ecf4ff", fontsize=18, family="DejaVu Sans")
    fig.text(0.11, 0.895, f"{demo_id} • percentile position inside actual lobby", color="#94aac4", fontsize=11)
    save(fig, out_dir / "real_multilens_radar.png")


def make_real_3d_signal_field(out_dir: Path, demo_id: str, ranked: pd.DataFrame) -> None:
    from mpl_toolkits.mplot3d import Axes3D  # noqa: F401

    cols = ["aim_process_global_score", "enc_low_vis_precision_retention", "enc_attacker_speed_mean"]
    work = ranked.copy()
    for c in cols:
        if c not in work.columns:
            return
    x = work[cols[0]].fillna(work[cols[0]].median()).to_numpy()
    y = work[cols[1]].fillna(work[cols[1]].median()).to_numpy()
    z = work[cols[2]].fillna(work[cols[2]].median()).to_numpy()
    c = work["risk"].fillna(0).to_numpy()

    fig = plt.figure(figsize=(10.8, 7.8), facecolor="#050910")
    ax = fig.add_subplot(111, projection="3d")
    ax.set_facecolor("#08101a")
    ax.scatter(x, y, z, c=c, cmap="turbo", s=80, alpha=0.9, edgecolors="none")
    top = np.nanargmax(c)
    ax.scatter([x[top]], [y[top]], [z[top]], s=220, c="#ffffff", alpha=0.25)
    ax.set_xlabel("aim-process", color="#c8d7e9", labelpad=12)
    ax.set_ylabel("low-vis retention", color="#c8d7e9", labelpad=12)
    ax.set_zlabel("movement mean", color="#c8d7e9", labelpad=8)
    ax.tick_params(colors="#9eb2ca")
    ax.xaxis.pane.set_facecolor((0.1, 0.14, 0.2, 0.08))
    ax.yaxis.pane.set_facecolor((0.1, 0.14, 0.2, 0.08))
    ax.zaxis.pane.set_facecolor((0.1, 0.14, 0.2, 0.08))
    fig.text(0.08, 0.94, "REAL 3D SIGNAL FIELD", color="#ecf4ff", fontsize=18)
    fig.text(0.08, 0.905, f"{demo_id} • actual lobby separation", color="#94aac4", fontsize=11)
    save(fig, out_dir / "real_signal_field_3d.png")


def make_real_dashboard(
    out_dir: Path,
    demo_id: str,
    ranked: pd.DataFrame,
    players: pd.DataFrame,
    top: pd.Series,
    top_player: pd.Series,
    player_enc: pd.DataFrame,
    player_name: str,
) -> None:
    fig = plt.figure(figsize=(16, 9), facecolor="#04070d")
    gs = GridSpec(3, 4, figure=fig, hspace=0.18, wspace=0.12)

    ax_main = fig.add_subplot(gs[:, :2])
    apply_dark_axis(ax_main)
    enc = player_enc.head(24).copy()
    if enc.empty:
        return
    x = np.arange(1, len(enc) + 1)
    y1 = enc["aim_error_at_first_visible"].fillna(0).to_numpy()
    y2 = enc["aim_error_min"].fillna(0).to_numpy()
    ax_main.plot(x, y1, color="#8deaff", linewidth=3.0, label="Aim error at first visible")
    ax_main.plot(x, y2, color="#ffb55d", linewidth=2.1, alpha=0.86, label="Aim error minimum")
    ax_main.fill_between(x, y1, np.minimum(y2.min(), y1.min()) - 0.5, color=(0.5, 0.9, 1, 0.06))
    ax_main.legend(loc="upper left", frameon=False, labelcolor="#dce7f5")
    neon_text(ax_main, 0.02, 1.04, f"REAL NULLCS DASHBOARD • {player_name}", size=21, va="bottom", transform=ax_main.transAxes)
    neon_text(ax_main, 0.02, 1.0, f"{demo_id} • actual encounter telemetry", color="#94aac4", size=11, va="bottom", transform=ax_main.transAxes)
    ax_main.set_xlabel("Encounter sequence")
    ax_main.set_ylabel("Aim error")

    ax_ring = fig.add_subplot(gs[0, 2], projection="polar")
    ax_ring.set_facecolor("#08101a")
    ring_labels = ["Signal", "Support", "NN", "Difficulty", "Timing", "Process"]
    ring_vals = np.array([
        min(float(top.get("risk", 0.0)), 1.0),
        min(float(top_player.get("enc_kill_end_rate", 0.0)), 1.0),
        min(float(top_player.get("enn_score_mean", 0.0)), 1.0),
        min(float(top_player.get("enc_precision_under_difficulty", 0.0)), 1.0),
        min(float(top_player.get("rt_median_pct", 0.0)), 1.0),
        min(float(top_player.get("enc_process_abnormality", 0.0)), 1.0),
    ])
    ring_angles = np.linspace(0, 2 * np.pi, len(ring_labels) + 1)
    ring_vals = np.concatenate([ring_vals, [ring_vals[0]]])
    ax_ring.plot(ring_angles, ring_vals, color="#7ee8ff", linewidth=2.3)
    ax_ring.fill(ring_angles, ring_vals, color=(0.45, 0.9, 1, 0.12))
    ax_ring.set_xticks(ring_angles[:-1])
    ax_ring.set_xticklabels(ring_labels, color="#dfe9f5", fontsize=9)
    ax_ring.set_yticks([])
    ax_ring.grid(color=(1, 1, 1, 0.08))
    ax_ring.spines["polar"].set_color((1, 1, 1, 0.1))
    ax_ring.set_title("Actual signal ring", color="#e8f2ff", fontsize=13, pad=16)

    ax_heat = fig.add_subplot(gs[0, 3])
    heat_cols = [
        "visible_ratio",
        "time_to_first_shot",
        "attacker_speed_mean",
        "aim_error_at_first_visible",
        "aim_error_min",
        "pre_shot_mouse_burst_max",
        "los_angular_velocity_mean",
    ]
    heat = enc[heat_cols].copy().fillna(0)
    heat = heat.apply(norm_series)
    ax_heat.imshow(heat.T, cmap="magma", aspect="auto")
    ax_heat.set_facecolor("#08101a")
    ax_heat.set_xticks([])
    ax_heat.set_yticks(range(len(heat_cols)))
    ax_heat.set_yticklabels(
        ["vis", "ttfshot", "speed", "err vis", "err min", "burst", "los vel"],
        color="#cfe0f4",
        fontsize=8,
    )
    ax_heat.set_title("Encounter heat matrix", color="#e8f2ff", fontsize=13, pad=12)

    ax_bars = fig.add_subplot(gs[1, 2:])
    apply_dark_axis(ax_bars)
    labels = ["Risk", "NN mean", "Low-vis", "Hard", "Process", "Difficulty"]
    vals = [
        float(top.get("risk", 0.0)),
        float(top_player.get("enn_score_mean", 0.0)),
        float(top_player.get("enn_low_vis_mean", 0.0)),
        float(top_player.get("enn_hard_mean", 0.0)),
        float(top_player.get("enc_process_abnormality", 0.0)),
        float(top_player.get("enc_precision_under_difficulty", 0.0)),
    ]
    vals = [min(max(v, 0.0), 1.0) for v in vals]
    ax_bars.barh(labels, vals, color=["#84eaff", "#ffb55d", "#7adca5", "#ff8d94", "#a4b6ff", "#c8d1dc"])
    ax_bars.set_xlim(0, 1)
    ax_bars.set_title("Actual evidence weight", color="#e8f2ff", fontsize=13, pad=12)

    ax_trace = fig.add_subplot(gs[2, 2])
    apply_dark_axis(ax_trace)
    tx = np.arange(1, len(enc) + 1)
    ty = enc["pre_shot_mouse_burst_max"].fillna(0).to_numpy()
    ax_trace.plot(tx, ty, color="#7ee8ff", linewidth=2.4)
    ax_trace.fill_between(tx, ty, 0, color=(0.5, 0.9, 1.0, 0.08))
    ax_trace.set_xticks([])
    ax_trace.set_yticks([])
    ax_trace.set_title("Mouse burst trace", color="#e8f2ff", fontsize=13, pad=12)

    ax_small = fig.add_subplot(gs[2, 3])
    apply_dark_axis(ax_small)
    lobby = ranked.sort_values("risk", ascending=False).head(10)
    sx = np.arange(len(lobby))
    sy = lobby["risk"].fillna(0).to_numpy()
    ax_small.plot(sx, sy, color="#ffb55d", linewidth=2.6)
    ax_small.scatter(sx, sy, color="#fff0d2", s=18)
    ax_small.set_xticks(sx)
    ax_small.set_xticklabels(lobby["attacker_name"].astype(str).str.slice(0, 6), rotation=35, ha="right", color="#a7b7cc", fontsize=7)
    ax_small.set_yticks([])
    ax_small.set_title("Lobby risk ladder", color="#e8f2ff", fontsize=13, pad=12)

    save(fig, out_dir / "real_nullcs_dashboard.png")


def make_real_aim_collapse_trace(out_dir: Path, demo_id: str, player_name: str, player_enc: pd.DataFrame) -> None:
    enc = player_enc.head(18).copy()
    if enc.empty:
        return
    x = np.arange(1, len(enc) + 1)
    first_vis = enc["aim_error_at_first_visible"].fillna(0).to_numpy()
    minimum = enc["aim_error_min"].fillna(0).to_numpy()
    lag = norm_series(enc["acquire_to_shot_lag"].fillna(enc["acquire_to_shot_lag"].median()))

    fig, ax = plt.subplots(figsize=(12, 6.6), facecolor="#050910")
    apply_dark_axis(ax)
    ax.plot(x, first_vis, color="#7ee8ff", linewidth=2.8, label="Error at first visible")
    ax.plot(x, minimum, color="#ffb55d", linewidth=2.4, label="Minimum error")
    ax.fill_between(x, first_vis, minimum, color=(0.45, 0.9, 1, 0.08))
    ax2 = ax.twinx()
    ax2.plot(x, lag, color="#bdf8c7", linewidth=1.8, linestyle="--", label="Normalized acquire-to-shot lag")
    ax2.set_ylim(0, 1)
    ax2.tick_params(colors="#9eb2ca", labelsize=8)
    for spine in ax2.spines.values():
        spine.set_color((1, 1, 1, 0.08))
    neon_text(ax, 0.02, 1.04, f"AIM ERROR COLLAPSE • {player_name}", size=18, va="bottom", transform=ax.transAxes)
    neon_text(ax, 0.02, 1.0, f"{demo_id} • real per-encounter acquisition collapse", color="#94aac4", size=11, va="bottom", transform=ax.transAxes)
    ax.set_xlabel("Encounter index", color="#b7c6d8")
    ax.set_ylabel("Angular error", color="#b7c6d8")
    ax.legend(loc="upper left", frameon=False, labelcolor="#dce7f5")
    save(fig, out_dir / "real_aim_collapse_trace.png")


def make_real_target_acquire_ladder(out_dir: Path, demo_id: str, player_name: str, player_enc: pd.DataFrame) -> None:
    enc = player_enc.head(14).copy()
    if enc.empty:
        return
    idx = np.arange(len(enc))
    width = 0.25
    acquire = enc["aim_acquire_time"].fillna(0).to_numpy()
    dwell = enc["aim_dwell_ticks"].fillna(0).to_numpy()
    lag = enc["acquire_to_shot_lag"].fillna(0).to_numpy()

    fig, ax = plt.subplots(figsize=(12, 6.4), facecolor="#060a12")
    apply_dark_axis(ax)
    ax.bar(idx - width, acquire, width=width, color="#7ee8ff", label="Acquire time")
    ax.bar(idx, dwell, width=width, color="#ffb55d", label="Dwell ticks")
    ax.bar(idx + width, lag, width=width, color="#b9f7c2", label="Acquire-to-shot lag")
    ax.set_xticks(idx)
    ax.set_xticklabels([str(i + 1) for i in idx], color="#b7c6d8")
    ax.set_xlabel("Encounter index", color="#b7c6d8")
    ax.set_ylabel("Ticks", color="#b7c6d8")
    ax.legend(loc="upper right", frameon=False, labelcolor="#dce7f5")
    neon_text(ax, 0.02, 1.04, f"TARGET ACQUIRE LADDER • {player_name}", size=18, va="bottom", transform=ax.transAxes)
    neon_text(ax, 0.02, 1.0, f"{demo_id} • acquire, dwell, and fire timing from actual encounters", color="#94aac4", size=11, va="bottom", transform=ax.transAxes)
    save(fig, out_dir / "real_target_acquire_ladder.png")


def make_real_low_vis_heatmap(out_dir: Path, demo_id: str, player_name: str, player_enc: pd.DataFrame) -> None:
    enc = player_enc.head(20).copy()
    if enc.empty:
        return
    cols = [
        "visible_ratio",
        "occluded_tick_count",
        "time_to_first_shot",
        "aim_error_at_first_visible",
        "aim_error_min",
        "los_angular_velocity_mean",
        "pre_shot_mouse_burst_max",
    ]
    labels = ["vis ratio", "occlusion", "ttf shot", "err vis", "err min", "los vel", "mouse burst"]
    heat = enc[cols].copy().fillna(0)
    heat = heat.apply(norm_series)

    fig, ax = plt.subplots(figsize=(11.5, 5.6), facecolor="#050910")
    ax.set_facecolor("#08101a")
    im = ax.imshow(heat.T, cmap="magma", aspect="auto")
    ax.set_xticks(np.arange(len(enc)))
    ax.set_xticklabels([str(i + 1) for i in range(len(enc))], color="#a7b7cc", fontsize=8)
    ax.set_yticks(np.arange(len(labels)))
    ax.set_yticklabels(labels, color="#dce7f5", fontsize=9)
    for spine in ax.spines.values():
        spine.set_color((1, 1, 1, 0.08))
    neon_text(ax, 0.015, 1.06, f"LOW-VIS / OCCLUSION HEATMAP • {player_name}", size=18, va="bottom", transform=ax.transAxes)
    neon_text(ax, 0.015, 1.015, f"{demo_id} • actual occlusion and pre-shot context", color="#94aac4", size=11, va="bottom", transform=ax.transAxes)
    cbar = fig.colorbar(im, ax=ax, fraction=0.03, pad=0.02)
    cbar.ax.tick_params(colors="#a7b7cc", labelsize=8)
    cbar.outline.set_edgecolor((1, 1, 1, 0.08))
    save(fig, out_dir / "real_low_vis_heatmap.png")


def make_real_round_pulse_timeline(out_dir: Path, demo_id: str, player_name: str, top_player: pd.Series, player_enc: pd.DataFrame) -> None:
    if player_enc.empty or "round_num" not in player_enc.columns:
        return
    grouped = (
        player_enc.groupby("round_num", as_index=False)
        .agg(
            encounters=("encounter_id", "count"),
            mean_visible_ratio=("visible_ratio", "mean"),
            mean_burst=("pre_shot_mouse_burst_max", "mean"),
            mean_lag=("acquire_to_shot_lag", "mean"),
            kill_end_rate=("ended_in_kill_within_y", "mean"),
        )
        .sort_values("round_num")
    )
    rounds = grouped["round_num"].to_numpy()
    pulse = norm_series(grouped["encounters"] * 0.35 + grouped["mean_burst"] * 0.05 + grouped["kill_end_rate"] * 3.0)
    vis = norm_series(grouped["mean_visible_ratio"])
    lag = 1.0 - norm_series(grouped["mean_lag"].fillna(grouped["mean_lag"].median()))

    fig, ax = plt.subplots(figsize=(12, 6.2), facecolor="#050910")
    apply_dark_axis(ax)
    ax.bar(rounds, pulse, color="#7ee8ff", alpha=0.35, width=0.8, label="Anomaly pulse")
    ax.plot(rounds, vis, color="#ffb55d", linewidth=2.2, label="Visibility retention")
    ax.plot(rounds, lag, color="#b9f7c2", linewidth=2.0, label="Timing sharpness")
    ax.set_xlabel("Round", color="#b7c6d8")
    ax.set_ylabel("Normalized intensity", color="#b7c6d8")
    ax.set_ylim(0, 1.05)
    ax.legend(loc="upper left", frameon=False, labelcolor="#dce7f5")
    neon_text(ax, 0.02, 1.04, f"ROUND PULSE TIMELINE • {player_name}", size=18, va="bottom", transform=ax.transAxes)
    neon_text(ax, 0.02, 1.0, f"{demo_id} • round-level signal concentration from real encounters", color="#94aac4", size=11, va="bottom", transform=ax.transAxes)
    save(fig, out_dir / "real_round_pulse_timeline.png")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate actual data-driven trailer plots from processed NullCS artifacts.")
    parser.add_argument("--demo-id", help="Processed demo/report id to render. Defaults to latest report.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    demo_id = args.demo_id or latest_demo_id()
    out_dir = OUT_ROOT / demo_id
    ensure_dir(out_dir)
    print(f"[INFO] using demo {demo_id}")
    print(f"[INFO] writing real trailer visuals to {out_dir}")
    ranked, players, encounters, top, top_player, player_enc, player_name = load_data(demo_id)
    make_real_aim_trace(out_dir, demo_id, player_name, player_enc)
    make_real_visibility_timeline(out_dir, demo_id, player_name, player_enc)
    make_real_radar(out_dir, demo_id, player_name, players, top_player)
    make_real_3d_signal_field(out_dir, demo_id, ranked)
    make_real_dashboard(out_dir, demo_id, ranked, players, top, top_player, player_enc, player_name)
    make_real_aim_collapse_trace(out_dir, demo_id, player_name, player_enc)
    make_real_target_acquire_ladder(out_dir, demo_id, player_name, player_enc)
    make_real_low_vis_heatmap(out_dir, demo_id, player_name, player_enc)
    make_real_round_pulse_timeline(out_dir, demo_id, player_name, top_player, player_enc)
    print("[DONE] real trailer pack generated")


if __name__ == "__main__":
    main()

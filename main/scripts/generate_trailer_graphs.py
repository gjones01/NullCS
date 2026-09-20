from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib import patheffects
from matplotlib.collections import LineCollection
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.gridspec import GridSpec


OUT_DIR = Path(r"C:\NullCS\docs\assets\trailer")
SEED = 7


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


def make_aim_trace() -> None:
    rng = np.random.default_rng(SEED)
    t = np.linspace(0, 1.0, 420)
    base_x = np.cumsum(rng.normal(0.0, 0.03, size=t.size))
    base_y = np.cumsum(rng.normal(0.0, 0.022, size=t.size))
    base_x += 0.35 * np.sin(t * 7.5) + 0.08 * np.sin(t * 31)
    base_y += 0.18 * np.cos(t * 5.5) + 0.05 * np.cos(t * 24)
    lock = np.exp(-((t - 0.72) ** 2) / 0.0025)
    base_x += lock * 1.3
    base_y -= lock * 0.85
    x = (base_x - base_x.min()) / (base_x.max() - base_x.min())
    y = (base_y - base_y.min()) / (base_y.max() - base_y.min())

    points = np.array([x, y]).T.reshape(-1, 1, 2)
    segments = np.concatenate([points[:-1], points[1:]], axis=1)
    cmap = LinearSegmentedColormap.from_list("nullcs_aim", ["#7ee8ff", "#b8f5c2", "#ffb65a", "#ff7d90"])

    fig, ax = plt.subplots(figsize=(11.5, 6.8), facecolor="#050910")
    ax.set_facecolor("#07101a")
    lc = LineCollection(segments, cmap=cmap, norm=plt.Normalize(t.min(), t.max()))
    lc.set_array(t)
    lc.set_linewidth(3.4)
    ax.add_collection(lc)
    ax.scatter(x[::8], y[::8], c=t[::8], cmap=cmap, s=8, alpha=0.8)
    ax.scatter([x[-1]], [y[-1]], s=220, c="#ffffff", alpha=0.08)
    ax.scatter([x[-1]], [y[-1]], s=52, c="#fefefe", edgecolors="#8be9ff", linewidths=1.6)
    ax.axvline(x=0.78, color=(0.7, 0.92, 1, 0.18), linestyle="--", linewidth=1.0)
    ax.axhline(y=0.43, color=(0.7, 0.92, 1, 0.08), linestyle="-", linewidth=0.8)
    neon_text(ax, 0.02, 0.96, "AIM TRACE / ACQUIRE PATH", size=18, va="top")
    neon_text(ax, 0.02, 0.905, "crosshair displacement over encounter window", color="#94aac4", size=11, va="top")
    neon_text(ax, x[-1] - 0.02, y[-1] + 0.05, "lock window", color="#ffd89c", size=10, ha="right")
    neon_text(ax, 0.81, 0.10, "acquire collapse\n0.18s", color="#8ef0ff", size=12)
    ax.set_xlim(-0.03, 1.03)
    ax.set_ylim(-0.03, 1.03)
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)
    save(fig, OUT_DIR / "aim_trace_hud.png")


def make_visibility_timeline() -> None:
    rng = np.random.default_rng(SEED + 1)
    x = np.arange(1, 31)
    visibility = np.clip(0.52 + 0.22 * np.sin(x / 2.4) + rng.normal(0, 0.035, x.size), 0.06, 0.96)
    movement = np.clip(0.41 + 0.18 * np.cos(x / 3.1) + rng.normal(0, 0.04, x.size), 0.05, 0.95)
    preaim = np.clip(0.28 + 0.38 * np.exp(-((x - 22) ** 2) / 18) + rng.normal(0, 0.03, x.size), 0.02, 0.95)

    fig, ax = plt.subplots(figsize=(11.5, 6.4), facecolor="#060a12")
    apply_dark_axis(ax)
    ax.fill_between(x, visibility, color=(0.45, 0.9, 1.0, 0.08))
    ax.plot(x, visibility, color="#7ee8ff", linewidth=2.4, label="Visibility context")
    ax.plot(x, movement, color="#b9f7c2", linewidth=2.0, label="Movement pressure")
    ax.plot(x, preaim, color="#ffb55d", linewidth=2.0, label="Pre-aim / anticipation")
    ax.scatter([22], [preaim[21]], s=90, color="#fff1c1", edgecolors="#ffb55d", linewidths=1.2, zorder=4)
    ax.set_xlim(1, 30)
    ax.set_ylim(0, 1.0)
    ax.set_xlabel("Encounter index", color="#b7c6d8")
    ax.set_ylabel("Normalized intensity", color="#b7c6d8")
    ax.legend(loc="upper left", frameon=False, labelcolor="#dce7f5")
    neon_text(ax, 0.015, 1.045, "VISIBILITY / MOVEMENT CONTEXT", size=18, va="bottom", transform=ax.transAxes)
    neon_text(ax, 0.015, 1.005, "sequence overlap across visibility, movement, and anticipatory pressure", color="#94aac4", size=11, va="bottom", transform=ax.transAxes)
    neon_text(ax, 22.5, preaim[21] + 0.08, "anticipatory spike", color="#ffd89c", size=10)
    save(fig, OUT_DIR / "visibility_context_timeline.png")


def make_radar_panel() -> None:
    labels = [
        "Process",
        "Occlusion",
        "Timing",
        "Difficulty",
        "Stability",
        "Concentration",
    ]
    values = np.array([0.78, 0.62, 0.83, 0.74, 0.57, 0.68])
    base = np.array([0.34, 0.28, 0.36, 0.31, 0.42, 0.39])
    angles = np.linspace(0, 2 * np.pi, len(labels), endpoint=False)
    angles = np.concatenate([angles, [angles[0]]])
    values = np.concatenate([values, [values[0]]])
    base = np.concatenate([base, [base[0]]])

    fig = plt.figure(figsize=(8.2, 8.2), facecolor="#060a12")
    ax = plt.subplot(111, polar=True)
    ax.set_facecolor("#08101a")
    ax.plot(angles, base, color="#6d87a5", linewidth=1.6, alpha=0.7)
    ax.fill(angles, base, color=(0.45, 0.55, 0.7, 0.08))
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
    fig.text(0.11, 0.93, "MULTI-LENS BEHAVIOR RADAR", color="#ecf4ff", fontsize=18, family="DejaVu Sans")
    fig.text(0.11, 0.895, "stacked encounter signal against contextual baseline", color="#94aac4", fontsize=11)
    save(fig, OUT_DIR / "multilens_radar.png")


def make_3d_signal_field() -> None:
    from mpl_toolkits.mplot3d import Axes3D  # noqa: F401

    rng = np.random.default_rng(SEED + 2)
    n = 140
    x = rng.normal(0.0, 0.8, n)
    y = rng.normal(0.0, 0.7, n)
    z = rng.normal(0.0, 0.65, n)
    x[:16] += np.linspace(0.4, 2.6, 16)
    y[:16] += np.linspace(0.2, 1.8, 16)
    z[:16] += np.linspace(0.3, 1.4, 16)
    c = np.sqrt((x - x.mean()) ** 2 + (y - y.mean()) ** 2 + (z - z.mean()) ** 2)

    fig = plt.figure(figsize=(10.8, 7.8), facecolor="#050910")
    ax = fig.add_subplot(111, projection="3d")
    ax.set_facecolor("#08101a")
    ax.scatter(x, y, z, c=c, cmap="turbo", s=28, alpha=0.82, edgecolors="none")
    ax.scatter(x[:4], y[:4], z[:4], s=110, c="#ffffff", alpha=0.28)
    ax.set_xlabel("process anomaly", color="#c8d7e9", labelpad=12)
    ax.set_ylabel("visibility pressure", color="#c8d7e9", labelpad=12)
    ax.set_zlabel("movement divergence", color="#c8d7e9", labelpad=8)
    ax.tick_params(colors="#9eb2ca")
    ax.xaxis.pane.set_facecolor((0.1, 0.14, 0.2, 0.08))
    ax.yaxis.pane.set_facecolor((0.1, 0.14, 0.2, 0.08))
    ax.zaxis.pane.set_facecolor((0.1, 0.14, 0.2, 0.08))
    ax.xaxis.pane.set_edgecolor((1, 1, 1, 0.06))
    ax.yaxis.pane.set_edgecolor((1, 1, 1, 0.06))
    ax.zaxis.pane.set_edgecolor((1, 1, 1, 0.06))
    fig.text(0.08, 0.94, "3D SIGNAL FIELD", color="#ecf4ff", fontsize=18)
    fig.text(0.08, 0.905, "multidimensional separation for trailer overlays", color="#94aac4", fontsize=11)
    save(fig, OUT_DIR / "signal_field_3d.png")


def make_dashboard() -> None:
    rng = np.random.default_rng(SEED + 3)
    fig = plt.figure(figsize=(16, 9), facecolor="#04070d")
    gs = GridSpec(3, 4, figure=fig, hspace=0.18, wspace=0.12)

    ax_main = fig.add_subplot(gs[:, :2])
    apply_dark_axis(ax_main)
    x = np.arange(1, 25)
    y1 = np.cumsum(rng.normal(0.15, 0.22, x.size)) + np.linspace(1.2, 8.5, x.size)
    y2 = np.cumsum(rng.normal(0.09, 0.16, x.size)) + np.linspace(0.8, 5.9, x.size)
    ax_main.plot(x, y1, color="#8deaff", linewidth=3.0)
    ax_main.plot(x, y2, color="#ffb55d", linewidth=2.1, alpha=0.86)
    ax_main.fill_between(x, y1, y2.min() - 1, color=(0.5, 0.9, 1, 0.06))
    neon_text(ax_main, 0.02, 1.04, "NULLCS FORENSIC DASHBOARD", size=21, va="bottom", transform=ax_main.transAxes)
    neon_text(ax_main, 0.02, 1.0, "behavior-first telemetry surfaces for trailer cutaways", color="#94aac4", size=11, va="bottom", transform=ax_main.transAxes)
    ax_main.set_xlabel("Encounter sequence")
    ax_main.set_ylabel("Composite anomaly")

    ax_ring = fig.add_subplot(gs[0, 2], projection="polar")
    ax_ring.set_facecolor("#08101a")
    ring_angles = np.linspace(0, 2 * np.pi, 7)
    ring_vals = np.array([0.81, 0.74, 0.69, 0.83, 0.58, 0.77, 0.81])
    ax_ring.plot(ring_angles, ring_vals, color="#7ee8ff", linewidth=2.3)
    ax_ring.fill(ring_angles, ring_vals, color=(0.45, 0.9, 1, 0.12))
    ax_ring.set_xticks([])
    ax_ring.set_yticks([])
    ax_ring.grid(color=(1, 1, 1, 0.08))
    ax_ring.spines["polar"].set_color((1, 1, 1, 0.1))
    ax_ring.set_title("Signal ring", color="#e8f2ff", fontsize=13, pad=16)

    ax_heat = fig.add_subplot(gs[0, 3])
    heat = rng.normal(0, 1, (24, 42))
    hot = np.exp(-(((np.arange(42)[None, :] - 27) ** 2) + ((np.arange(24)[:, None] - 13) ** 2)) / 62)
    heat = heat * 0.4 + hot * 2.2
    ax_heat.imshow(heat, cmap="magma", aspect="auto")
    ax_heat.set_facecolor("#08101a")
    ax_heat.set_xticks([])
    ax_heat.set_yticks([])
    ax_heat.set_title("Visibility pressure map", color="#e8f2ff", fontsize=13, pad=12)

    ax_bars = fig.add_subplot(gs[1, 2:])
    apply_dark_axis(ax_bars)
    labels = ["Aim", "Info", "Motion", "Timing", "Occlusion", "Context"]
    vals = [0.61, 0.76, 0.42, 0.69, 0.58, 0.33]
    ax_bars.barh(labels, vals, color=["#84eaff", "#ffb55d", "#7adca5", "#ff8d94", "#a4b6ff", "#c8d1dc"])
    ax_bars.set_xlim(0, 1)
    ax_bars.set_title("Evidence component weight", color="#e8f2ff", fontsize=13, pad=12)

    ax_trace = fig.add_subplot(gs[2, 2])
    apply_dark_axis(ax_trace)
    tx = np.linspace(0, 1, 140)
    ty = 0.35 + 0.22 * np.sin(tx * 11) + 0.31 * np.exp(-((tx - 0.68) ** 2) / 0.011)
    ax_trace.plot(tx, ty, color="#7ee8ff", linewidth=2.4)
    ax_trace.fill_between(tx, ty, 0, color=(0.5, 0.9, 1.0, 0.08))
    ax_trace.set_xticks([])
    ax_trace.set_yticks([])
    ax_trace.set_title("Aim collapse", color="#e8f2ff", fontsize=13, pad=12)

    ax_small = fig.add_subplot(gs[2, 3])
    apply_dark_axis(ax_small)
    sx = np.arange(12)
    sy = np.array([12, 18, 15, 22, 21, 19, 26, 31, 28, 34, 37, 44])
    ax_small.plot(sx, sy, color="#ffb55d", linewidth=2.6)
    ax_small.scatter(sx, sy, color="#fff0d2", s=18)
    ax_small.set_xticks([])
    ax_small.set_yticks([])
    ax_small.set_title("Support ramp", color="#e8f2ff", fontsize=13, pad=12)

    save(fig, OUT_DIR / "nullcs_trailer_dashboard.png")


def main() -> None:
    ensure_dir(OUT_DIR)
    print(f"[INFO] writing trailer visuals to {OUT_DIR}")
    make_aim_trace()
    make_visibility_timeline()
    make_radar_panel()
    make_3d_signal_field()
    make_dashboard()
    print("[DONE] trailer pack generated")
    print("[DONE] trailer pack generated")


if __name__ == "__main__":
    main()

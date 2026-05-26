from __future__ import annotations

from pathlib import Path
import argparse
import json
import re
import math
import sys
import numpy as np
import pandas as pd
import polars as pl

PROJECT_ROOT = Path(__file__).resolve().parents[2]  # .../main
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.utils.project_paths import DEMOS_ROOT, PROCESSED_ROOT
from src.utils.training_mode import player_features_path, player_features_summary_path, resolve_train_data_mode, source_of_demo_id
from src.models.encounter_nn import encounter_player_feature_path

# -------- CONFIG --------
IN_ROOT = DEMOS_ROOT
OUT_PATH = PROCESSED_ROOT / "player_features.parquet"
CHEATER_CSV = PROCESSED_ROOT / "CheaterSteamIDs.csv"

MIN_KILLS = 5
FAST_RT_TICKS = 8
LONG_RANGE_DIST = 1500.0
LAPLACE_ALPHA = 1.0
SHRINK_K = 10.0
MIN_RT_EVIDENCE = 8
OVERWRITE = True
# ------------------------

ENCOUNTER_FEATURE_SPECS = {
    "exposure_duration": {"prefix": "enc_exposure", "low": 16.0, "high": 96.0},
    "visible_ratio": {"prefix": "enc_visible_ratio", "low": 0.55, "high": 0.95},
    "time_to_first_shot": {"prefix": "enc_ttfshot", "low": 4.0, "high": 24.0},
    "time_to_first_damage": {"prefix": "enc_ttdmg", "low": 6.0, "high": 32.0},
    "aim_error_at_first_visible": {"prefix": "enc_aim_error_visible", "low": 3.0, "high": 15.0},
    "aim_error_min": {"prefix": "enc_aim_error_min", "low": 1.5, "high": 8.0},
    "aim_acquire_time": {"prefix": "enc_aim_acquire", "low": 4.0, "high": 20.0},
    "aim_dwell_ticks": {"prefix": "enc_aim_dwell", "low": 2.0, "high": 24.0},
    "aim_error_range": {"prefix": "enc_aim_range", "low": 2.0, "high": 20.0},
    "aim_error_collapse_rate": {"prefix": "enc_aim_collapse_rate", "low": 0.05, "high": 2.0},
    "aim_error_collapse_ratio": {"prefix": "enc_aim_collapse_ratio", "low": 1.2, "high": 8.0},
    "aim_error_min_tick_offset": {"prefix": "enc_aim_min_tick", "low": 1.0, "high": 32.0},
    "aim_correction_flips": {"prefix": "enc_aim_flips", "low": 0.0, "high": 4.0},
    "post_acquire_error_mean": {"prefix": "enc_post_acquire_err", "low": 0.2, "high": 4.0},
    "post_acquire_error_std": {"prefix": "enc_post_acquire_err_std", "low": 0.05, "high": 2.5},
    "pre_shot_aim_error_mean": {"prefix": "enc_preshot_err", "low": 0.2, "high": 6.0},
    "pre_shot_aim_error_std": {"prefix": "enc_preshot_err_std", "low": 0.05, "high": 2.5},
    "acquire_to_shot_lag": {"prefix": "enc_acquire_shot_lag", "low": 0.0, "high": 12.0},
    "snap_velocity_early_max": {"prefix": "enc_snap_vel_early", "low": 0.5, "high": 12.0},
    "snap_velocity_to_shot_max": {"prefix": "enc_snap_vel_shot", "low": 0.5, "high": 12.0},
    "snap_jerk_early_max": {"prefix": "enc_snap_jerk_early", "low": 0.05, "high": 6.0},
    "snap_jerk_to_shot_max": {"prefix": "enc_snap_jerk_shot", "low": 0.05, "high": 6.0},
    "mouse_delta_abs_mean": {"prefix": "enc_mouse_delta", "low": 0.25, "high": 8.0},
    "mouse_delta_abs_p90": {"prefix": "enc_mouse_delta_p90", "low": 0.5, "high": 16.0},
    "mouse_delta_abs_max": {"prefix": "enc_mouse_delta_max", "low": 1.0, "high": 24.0},
    "mouse_delta_abs_std": {"prefix": "enc_mouse_delta_std", "low": 0.05, "high": 8.0},
    "mouse_dx_flip_rate": {"prefix": "enc_mouse_dx_flip", "low": 0.05, "high": 0.75},
    "mouse_dy_flip_rate": {"prefix": "enc_mouse_dy_flip", "low": 0.05, "high": 0.75},
    "pre_shot_mouse_burst_max": {"prefix": "enc_mouse_burst", "low": 0.5, "high": 18.0},
    "post_acquire_mouse_quiet_rate": {"prefix": "enc_mouse_quiet", "low": 0.15, "high": 0.9},
    "walking_tick_rate": {"prefix": "enc_walking", "low": 0.05, "high": 0.8},
    "airborne_tick_rate": {"prefix": "enc_airborne", "low": 0.01, "high": 0.35},
    "angular_velocity_mean": {"prefix": "enc_ang_vel", "low": 0.25, "high": 3.0},
    "angular_jerk_mean": {"prefix": "enc_ang_jerk", "low": 0.05, "high": 0.75},
    "los_angular_velocity_mean": {"prefix": "enc_los_ang_vel", "low": 0.2, "high": 2.0},
    "los_angular_jerk_mean": {"prefix": "enc_los_ang_jerk", "low": 0.03, "high": 0.5},
    "distance_mean": {"prefix": "enc_distance", "low": 300.0, "high": 1800.0},
    "closing_speed_mean": {"prefix": "enc_closing_speed", "low": -1.0, "high": 2.0},
    "attacker_speed_mean": {"prefix": "enc_attacker_speed", "low": 0.3, "high": 12.0},
    "victim_speed_mean": {"prefix": "enc_victim_speed", "low": 0.3, "high": 12.0},
    "relative_speed_mean": {"prefix": "enc_relative_speed", "low": 0.5, "high": 16.0},
    "shot_count": {"prefix": "enc_shot_count", "low": 1.0, "high": 5.0},
    "shot_rate_per_128": {"prefix": "enc_shot_rate", "low": 1.0, "high": 8.0},
    "mean_shot_gap": {"prefix": "enc_shot_gap", "low": 2.0, "high": 16.0},
    "damage_count": {"prefix": "enc_damage_count", "low": 1.0, "high": 3.0},
    "damage_total": {"prefix": "enc_damage_total", "low": 20.0, "high": 100.0},
}


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Aggregate engagement rows into player-demo features.")
    ap.add_argument(
        "--train-data",
        default=None,
        help="Training data mode: local, cs2cd, or merged. Default resolves from env or merged.",
    )
    return ap.parse_args()


def safe_print(text: str) -> None:
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode("ascii", errors="replace").decode("ascii"))


def _split_steamids(raw: str) -> list[str]:
    # Support multiple IDs in one cell, e.g. "id1;id2|id3 id4".
    parts = re.split(r"[;,|\s]+", str(raw).strip())
    return [p.strip() for p in parts if p and p.strip()]


def load_cheater_map(csv_path: Path) -> dict[str, set[str]]:
    if not csv_path.exists():
        print(f"[WARN] Cheater CSV not found: {csv_path}")
        return {}

    df = pd.read_csv(csv_path, dtype=str)
    cols = {c.lower().strip(): c for c in df.columns}
    demo_col = cols.get("cdemo id") or cols.get("demo id") or cols.get("demo_id")
    id_col = cols.get("name/id") or cols.get("steamid") or cols.get("steam_id") or cols.get("attacker_steamid")
    id_cols: list[str] = []
    if id_col is not None:
        id_cols.append(id_col)
    for lc, orig in cols.items():
        if lc.startswith("steamid") or lc.startswith("steam_id") or lc.startswith("cheater_steamid"):
            if orig not in id_cols:
                id_cols.append(orig)

    if demo_col is None or not id_cols:
        raise ValueError(f"Cheater CSV must have demo+steamid columns. Found: {list(df.columns)}")

    df = df[[demo_col, *id_cols]].copy()
    df = df.rename(columns={demo_col: "demo_id"})
    df["demo_id"] = df["demo_id"].astype(str).str.strip()
    df = df[df["demo_id"] != ""]

    exploded = []
    for _, row in df.iterrows():
        demo_id = str(row["demo_id"]).strip()
        for col in id_cols:
            for sid in _split_steamids(row[col]):
                exploded.append((demo_id, sid))

    if not exploded:
        print(f"[WARN] Cheater CSV has no usable demo/steamid rows: {csv_path}")
        return {}

    edf = pd.DataFrame(exploded, columns=["demo_id", "cheater_steamid"]).drop_duplicates()
    mp = edf.groupby("demo_id")["cheater_steamid"].apply(set).to_dict()
    print(f"[INFO] loaded cheater map demos: {len(mp)} rows: {len(edf)} steamid_cols: {len(id_cols)} from {csv_path}")
    return mp


def demo_base_label(demo_id: str) -> int | None:
    d = demo_id.lower()
    if d.startswith("pro") or d.startswith("normal"):
        return 0
    if d.startswith("cdemo"):
        return None
    return None


def weapon_family(weapon: object) -> str:
    w = str(weapon).lower().strip()
    rifles = {"ak47", "m4a1", "m4a1_silencer", "famas", "galilar", "aug", "sg556"}
    pistols = {"glock", "hkp2000", "usp_silencer", "p250", "elite", "fiveseven", "tec9", "cz75a", "deagle", "revolver"}
    smgs = {"mac10", "mp9", "mp7", "mp5sd", "ump45", "p90", "bizon"}
    awp_smg = {"awp", "ssg08", *smgs}
    if w in rifles:
        return "rifle"
    if w in pistols:
        return "pistol"
    if w in awp_smg:
        return "awp_smg"
    return "other"


def laplace(success: float, trials: float, alpha: float = LAPLACE_ALPHA) -> float:
    if pd.isna(success) or pd.isna(trials):
        return np.nan
    return float((success + alpha) / (trials + (2.0 * alpha)))


def longest_true_streak(bools: list[bool]) -> int:
    best = 0
    cur = 0
    for b in bools:
        if b:
            cur += 1
            if cur > best:
                best = cur
        else:
            cur = 0
    return best


def longest_consecutive_int_streak(vals: list[int]) -> int:
    if not vals:
        return 0
    vals = sorted(set(vals))
    best = 1
    cur = 1
    for i in range(1, len(vals)):
        if vals[i] == vals[i - 1] + 1:
            cur += 1
            best = max(best, cur)
        else:
            cur = 1
    return best


def normalized_entropy_from_counts(counts: pd.Series) -> float:
    counts = pd.to_numeric(counts, errors="coerce").fillna(0.0)
    counts = counts[counts > 0]
    if counts.empty or len(counts) <= 1:
        return 0.0
    probs = counts / counts.sum()
    ent = float(-(probs * np.log(probs)).sum())
    return float(ent / math.log(len(probs)))


def normalized_entropy_from_list(counts: list[float] | None) -> float:
    if hasattr(counts, "to_list"):
        counts = counts.to_list()
    if not counts:
        return 0.0
    arr = np.asarray([float(x) for x in counts if x is not None and float(x) > 0], dtype=float)
    if arr.size <= 1:
        return 0.0
    probs = arr / arr.sum()
    ent = float(-(probs * np.log(probs)).sum())
    return float(ent / math.log(arr.size))


def label_demo_frame(
    df: pd.DataFrame,
    demo_id: str,
    source: str,
    cheater_map: dict[str, set[str]],
) -> pd.DataFrame | None:
    if df.empty:
        return None
    if "attacker_steamid" not in df.columns:
        print(f"[WARN] {demo_id}: missing attacker_steamid, skipping")
        return None

    base = demo_base_label(demo_id)
    is_cd = demo_id.lower().startswith("cdemo")

    df = df.copy()
    df["demo_id"] = demo_id
    df["dataset_source"] = source
    sid = df["attacker_steamid"].astype(str).str.strip()

    has_inline_label = "label" in df.columns and df["label"].notna().any()
    if has_inline_label:
        df["label"] = pd.to_numeric(df["label"], errors="coerce").fillna(0).astype(int)
    elif is_cd:
        cheater_ids = cheater_map.get(demo_id)
        if not cheater_ids:
            print(f"[WARN] {demo_id}: no cheater SteamID found in {CHEATER_CSV}. Skipping this demo.")
            return None
        df["label"] = sid.isin(cheater_ids).astype(int)
    else:
        if base is None:
            print(f"[WARN] {demo_id}: unknown naming. Skipping.")
            return None
        df["label"] = int(base)

    df["attacker_steamid"] = sid
    if "attacker_name" not in df.columns:
        df["attacker_name"] = ""
    if "map_name" not in df.columns:
        df["map_name"] = ""
    return df


def label_demo_frame_pl(
    df: pl.DataFrame,
    demo_id: str,
    source: str,
    cheater_map: dict[str, set[str]],
) -> pl.DataFrame | None:
    if df.is_empty():
        return None
    if "attacker_steamid" not in df.columns:
        print(f"[WARN] {demo_id}: missing attacker_steamid, skipping")
        return None

    base = demo_base_label(demo_id)
    is_cd = demo_id.lower().startswith("cdemo")
    sid_expr = pl.col("attacker_steamid").cast(pl.Utf8).str.strip_chars()

    out = df.with_columns(
        pl.lit(demo_id).alias("demo_id"),
        pl.lit(source).alias("dataset_source"),
        sid_expr.alias("attacker_steamid"),
    )

    has_inline_label = "label" in out.columns and out["label"].drop_nulls().len() > 0
    if has_inline_label:
        out = out.with_columns(pl.col("label").cast(pl.Float64, strict=False).fill_null(0).cast(pl.Int64))
    elif is_cd:
        cheater_ids = cheater_map.get(demo_id)
        if not cheater_ids:
            print(f"[WARN] {demo_id}: no cheater SteamID found in {CHEATER_CSV}. Skipping this demo.")
            return None
        out = out.with_columns(
            pl.col("attacker_steamid").is_in(sorted(cheater_ids)).cast(pl.Int64).alias("label")
        )
    else:
        if base is None:
            print(f"[WARN] {demo_id}: unknown naming. Skipping.")
            return None
        out = out.with_columns(pl.lit(int(base)).alias("label"))

    if "attacker_name" not in out.columns:
        out = out.with_columns(pl.lit("").alias("attacker_name"))
    if "map_name" not in out.columns:
        out = out.with_columns(pl.lit("").alias("map_name"))
    return out


def ensure_columns_pl(df: pl.DataFrame, defaults: list[tuple[str, object]]) -> pl.DataFrame:
    exprs: list[pl.Expr] = []
    for col, default in defaults:
        if col in df.columns:
            continue
        exprs.append(pl.lit(default).alias(col))
    return df.with_columns(exprs) if exprs else df


def _list_to_bools(values: object) -> list[bool]:
    if hasattr(values, "to_list"):
        values = values.to_list()
    if values is None:
        return []
    return [bool(x) for x in values]


def _list_to_ints(values: object) -> list[int]:
    if hasattr(values, "to_list"):
        values = values.to_list()
    if values is None:
        return []
    return [int(x) for x in values]


def build_row(g: pd.DataFrame) -> dict[str, object]:
    g = g.sort_values("kill_tick")

    rt = pd.to_numeric(g["rt_ticks"], errors="coerce")
    rt_valid = rt.dropna()
    rt_n = int(rt_valid.shape[0])
    n_kills = int(len(g))

    prefire_mask = (rt <= -2).fillna(False)
    thrusmoke_mask = g["is_thrusmoke"].fillna(False).astype(bool)
    hs_mask = g["headshot"].fillna(False).astype(bool)
    fast_rt_mask = (rt <= FAST_RT_TICKS).fillna(False)
    rt_le_2_mask = (rt <= 2).fillna(False)
    rt_le_4_mask = (rt <= 4).fillna(False)

    dist = pd.to_numeric(g["distance"], errors="coerce")
    long_range_mask = (dist >= LONG_RANGE_DIST) & rt.notna()
    long_fast_mask = long_range_mask & (rt <= FAST_RT_TICKS)
    long_fast_4_mask = long_range_mask & (rt <= 4)
    prefire_long_range_mask = prefire_mask & (dist >= LONG_RANGE_DIST)

    rounds = pd.to_numeric(g["round_num"], errors="coerce")
    rounds_played = int(rounds.dropna().nunique())

    thr_rounds = rounds[thrusmoke_mask].dropna().astype(int).tolist()
    thrusmoke_rounds = len(set(thr_rounds))
    max_thr_round_streak = longest_consecutive_int_streak(thr_rounds)

    thr_per_round = (
        g.assign(_thr=thrusmoke_mask.values)
        .groupby("round_num", dropna=True)["_thr"]
        .sum()
    )
    thrusmoke_repeat_rounds = int((thr_per_round >= 2).sum())

    victims = g["victim_steamid"].astype(str).str.strip()
    victim_n = int(victims.nunique())
    prefire_victim_n = int(victims[prefire_mask].nunique())

    wf = g["weapon"].apply(weapon_family)
    round_counts = rounds.dropna().astype(int).value_counts()
    weapon_counts = wf.value_counts()
    victim_counts = victims.value_counts()
    signal_mask = prefire_mask | thrusmoke_mask | long_fast_4_mask | g["is_micropeek_4"].fillna(False).astype(bool)
    signal_round_counts = rounds[signal_mask].dropna().astype(int).value_counts()
    round_vals = rounds.dropna().astype(int)
    if not round_vals.empty:
        late_round_cut = int(math.ceil(float(round_vals.min() + round_vals.max()) / 2.0))
        late_round_mask = rounds.fillna(-10**9).astype(int) >= late_round_cut
    else:
        late_round_cut = None
        late_round_mask = pd.Series(False, index=g.index)
    late_signal_mask = signal_mask & late_round_mask

    def fam_counts(f: str) -> tuple[int, int, int, int]:
        m = wf == f
        return (
            int(m.sum()),
            int((m & fast_rt_mask).sum()),
            int((m & prefire_mask).sum()),
            int((m & thrusmoke_mask).sum()),
        )

    rifle_n, rifle_fast_n, rifle_prefire_n, rifle_thr_n = fam_counts("rifle")
    pistol_n, pistol_fast_n, pistol_prefire_n, pistol_thr_n = fam_counts("pistol")
    awp_smg_n, awp_smg_fast_n, awp_smg_prefire_n, awp_smg_thr_n = fam_counts("awp_smg")

    row = {
        "demo_id": g["demo_id"].iloc[0],
        "map_name": g["map_name"].iloc[0],
        "attacker_steamid": g["attacker_steamid"].iloc[0],
        "attacker_name": g["attacker_name"].iloc[0],
        "label": int(g["label"].iloc[0]),
        "n_kills": n_kills,
        "n_kills_with_rt": rt_n,
        "rt_n": rt_n,
        "hs_n": n_kills,
        "smoke_n": n_kills,
        "rounds_played": rounds_played,
        "n_victims": victim_n,
        "rounds_with_kills": int(round_counts.shape[0]),
        "top_round_kill_share": float(round_counts.max() / n_kills) if n_kills else np.nan,
        "round_kill_entropy": normalized_entropy_from_counts(round_counts),
        "multi_kill_round_rate": laplace(float((round_counts >= 2).sum()), float(max(1, round_counts.shape[0]))),
        "top_signal_round_share": float(signal_round_counts.max() / max(1, int(signal_mask.sum()))) if int(signal_mask.sum()) else 0.0,
        "signal_round_entropy": normalized_entropy_from_counts(signal_round_counts),
        "late_round_cut": late_round_cut,
        "late_round_kill_share": float(late_round_mask.sum() / max(1, n_kills)) if n_kills else 0.0,
        "late_signal_share": float(late_signal_mask.sum() / max(1, int(signal_mask.sum()))) if int(signal_mask.sum()) else 0.0,
        "dominant_weapon_share": float(weapon_counts.max() / n_kills) if n_kills else np.nan,
        "weapon_entropy": normalized_entropy_from_counts(weapon_counts),
        "top_victim_share": float(victim_counts.max() / n_kills) if n_kills else np.nan,
        "victim_entropy": normalized_entropy_from_counts(victim_counts),
        "kill_density": float(n_kills / max(1, round_counts.shape[0])),
        "rt_mean": float(rt_valid.mean()) if rt_n else np.nan,
        "rt_median": float(rt_valid.median()) if rt_n else np.nan,
        "rt_p10": float(rt_valid.quantile(0.10, interpolation="nearest")) if rt_n else np.nan,
        "rt_p90": float(rt_valid.quantile(0.90, interpolation="nearest")) if rt_n else np.nan,
        "rt_std": float(rt_valid.std(ddof=1)) if rt_n > 1 else np.nan,
        "dist_mean": float(dist.mean()) if n_kills else np.nan,
        "dist_median": float(dist.median()) if n_kills else np.nan,
        "dist_p90": float(dist.quantile(0.90, interpolation="nearest")) if n_kills else np.nan,
        "weapon_n_unique": int(g["weapon"].astype(str).nunique()),
        "headshot_count": int(hs_mask.sum()),
        "fast_rt_count": int(fast_rt_mask.sum()),
        "rt_le_2_count": int(rt_le_2_mask.sum()),
        "rt_le_4_count": int(rt_le_4_mask.sum()),
        "prefire_count": int(prefire_mask.sum()),
        "prefire_long_range_count": int(prefire_long_range_mask.sum()),
        "prefire_victim_n": prefire_victim_n,
        "thrusmoke_kills": int(thrusmoke_mask.sum()),
        "thrusmoke_rounds": int(thrusmoke_rounds),
        "thrusmoke_repeat_rounds": int(thrusmoke_repeat_rounds),
        "max_thrusmoke_streak": int(longest_true_streak(thrusmoke_mask.tolist())),
        "max_thrusmoke_round_streak": int(max_thr_round_streak),
        "long_range_kills_with_rt": int(long_range_mask.sum()),
        "long_range_fast_rt_count": int(long_fast_mask.sum()),
        "long_range_fast_rt_4_count": int(long_fast_4_mask.sum()),
        "max_fast_rt_streak": int(longest_true_streak((rt <= 4).fillna(False).tolist())),
        "max_headshot_streak": int(longest_true_streak(hs_mask.tolist())),
        "max_prefire_streak": int(longest_true_streak(prefire_mask.tolist())),
        "rifle_kills": rifle_n,
        "pistol_kills": pistol_n,
        "awp_smg_kills": awp_smg_n,
        "rifle_fast_rt_count": rifle_fast_n,
        "pistol_fast_rt_count": pistol_fast_n,
        "awp_smg_fast_rt_count": awp_smg_fast_n,
        "rifle_prefire_count": rifle_prefire_n,
        "pistol_prefire_count": pistol_prefire_n,
        "awp_smg_prefire_count": awp_smg_prefire_n,
        "rifle_thrusmoke_count": rifle_thr_n,
        "pistol_thrusmoke_count": pistol_thr_n,
        "awp_smg_thrusmoke_count": awp_smg_thr_n,
    }
    return row


def _quantile_or_nan(s: pd.Series, q: float) -> float:
    s = pd.to_numeric(s, errors="coerce").dropna()
    if s.empty:
        return np.nan
    return float(s.quantile(q, interpolation="nearest"))


def _series_stats(series: pd.Series, low: float | None = None, high: float | None = None) -> dict[str, float]:
    s = pd.to_numeric(series, errors="coerce").dropna()
    n = int(len(s))
    if n == 0:
        return {
            "mean": np.nan,
            "median": np.nan,
            "p10": np.nan,
            "p90": np.nan,
            "std": np.nan,
            "low_rate": np.nan,
            "high_rate": np.nan,
        }
    return {
        "mean": float(s.mean()),
        "median": float(s.median()),
        "p10": _quantile_or_nan(s, 0.10),
        "p90": _quantile_or_nan(s, 0.90),
        "std": float(s.std(ddof=1)) if n > 1 else np.nan,
        "low_rate": laplace(float((s <= low).sum()), float(n)) if low is not None else np.nan,
        "high_rate": laplace(float((s >= high).sum()), float(n)) if high is not None else np.nan,
    }


def build_encounter_row(g: pd.DataFrame) -> dict[str, object]:
    g = g.sort_values("start_tick")
    encounter_n = int(len(g))

    row = {
        "demo_id": g["demo_id"].iloc[0],
        "map_name": g["map_name"].iloc[0],
        "attacker_steamid": g["attacker_steamid"].iloc[0],
        "attacker_name": g["attacker_name"].iloc[0],
        "label": int(g["label"].iloc[0]),
        "enc_n": encounter_n,
    }
    for source_col, cfg in ENCOUNTER_FEATURE_SPECS.items():
        if source_col not in g.columns:
            continue
        stats = _series_stats(g[source_col], cfg.get("low"), cfg.get("high"))
        prefix = cfg["prefix"]
        row[f"{prefix}_mean"] = stats["mean"]
        row[f"{prefix}_median"] = stats["median"]
        row[f"{prefix}_p10"] = stats["p10"]
        row[f"{prefix}_p90"] = stats["p90"]
        row[f"{prefix}_std"] = stats["std"]
        row[f"{prefix}_low_rate"] = stats["low_rate"]
        row[f"{prefix}_high_rate"] = stats["high_rate"]

    ended_kill = g["ended_in_kill_within_y"].fillna(False).astype(bool) if "ended_in_kill_within_y" in g.columns else pd.Series(dtype=bool)
    ended_damage = g["ended_in_damage"].fillna(False).astype(bool) if "ended_in_damage" in g.columns else pd.Series(dtype=bool)
    shot_before_acquire = g["shot_before_aim_acquire"].fillna(False).astype(bool) if "shot_before_aim_acquire" in g.columns else pd.Series(dtype=bool)

    row["enc_kill_end_rate"] = laplace(float(ended_kill.sum()), float(encounter_n))
    row["enc_damage_end_rate"] = laplace(float(ended_damage.sum()), float(encounter_n))
    row["enc_shot_before_acquire_rate"] = laplace(float(shot_before_acquire.sum()), float(encounter_n))
    row["enc_multi_damage_rate"] = laplace(float((pd.to_numeric(g.get("damage_count"), errors="coerce").fillna(0) >= 2).sum()), float(encounter_n))

    distance_mean = pd.to_numeric(g.get("distance_mean"), errors="coerce").fillna(0.0)
    rel_speed = pd.to_numeric(g.get("relative_speed_mean"), errors="coerce").fillna(0.0)
    att_speed = pd.to_numeric(g.get("attacker_speed_mean"), errors="coerce").fillna(0.0)
    vic_speed = pd.to_numeric(g.get("victim_speed_mean"), errors="coerce").fillna(0.0)
    visible_ratio = pd.to_numeric(g.get("visible_ratio"), errors="coerce").fillna(1.0)
    aim_err_min = pd.to_numeric(g.get("aim_error_min"), errors="coerce").fillna(999.0)
    aim_acq = pd.to_numeric(g.get("aim_acquire_time"), errors="coerce").fillna(999.0)
    pre_shot_err = pd.to_numeric(g.get("pre_shot_aim_error_mean"), errors="coerce").fillna(999.0)
    post_lock_std = pd.to_numeric(g.get("post_acquire_error_std"), errors="coerce").fillna(999.0)
    hard_mask = (distance_mean >= 900.0) | (rel_speed >= 6.0) | (att_speed >= 4.0) | (vic_speed >= 4.0) | (visible_ratio <= 0.75)
    hard_n = int(hard_mask.sum())
    easy_mask = ~hard_mask
    easy_n = int(easy_mask.sum())
    row["enc_hard_n"] = hard_n
    row["enc_easy_n"] = easy_n
    row["enc_hard_low_error_rate"] = laplace(float((hard_mask & (aim_err_min <= 0.9)).sum()), float(max(1, hard_n)))
    row["enc_hard_fast_acquire_rate"] = laplace(float((hard_mask & (aim_acq <= 4.0)).sum()), float(max(1, hard_n)))
    row["enc_hard_clean_preshot_rate"] = laplace(float((hard_mask & (pre_shot_err <= 1.25)).sum()), float(max(1, hard_n)))
    row["enc_hard_low_noise_rate"] = laplace(float((hard_mask & (post_lock_std <= 0.35)).sum()), float(max(1, hard_n)))
    row["enc_hard_finish_rate"] = laplace(float((hard_mask & ended_kill).sum()), float(max(1, hard_n)))
    row["enc_easy_low_error_rate"] = laplace(float((easy_mask & (aim_err_min <= 0.9)).sum()), float(max(1, easy_n)))
    row["enc_precision_under_difficulty"] = float(
        (
            row["enc_hard_low_error_rate"] * 0.34
            + row["enc_hard_fast_acquire_rate"] * 0.22
            + row["enc_hard_clean_preshot_rate"] * 0.20
            + row["enc_hard_low_noise_rate"] * 0.14
            + row["enc_hard_finish_rate"] * 0.10
        )
    )
    row["enc_difficulty_precision_gap"] = float(row["enc_hard_low_error_rate"] - row["enc_easy_low_error_rate"])
    return row


def aggregate_kill_and_encounter_frames(
    kill_df: pd.DataFrame,
    encounter_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    if isinstance(kill_df, pl.DataFrame):
        if kill_df.is_empty():
            return pd.DataFrame()
    elif kill_df.empty:
        return pd.DataFrame()

    key_cols = ["demo_id", "map_name", "attacker_steamid", "attacker_name", "label"]
    all_kills = pl.from_pandas(kill_df) if isinstance(kill_df, pd.DataFrame) else kill_df
    all_kills = all_kills.with_columns(
        pl.col("demo_id").cast(pl.Utf8),
        pl.col("map_name").cast(pl.Utf8),
        pl.col("attacker_steamid").cast(pl.Utf8).str.strip_chars(),
        pl.col("attacker_name").cast(pl.Utf8),
        pl.col("label").cast(pl.Int64),
        pl.col("victim_steamid").cast(pl.Utf8).fill_null("").alias("victim_steamid"),
        pl.col("weapon").cast(pl.Utf8).fill_null("").alias("weapon"),
        pl.col("kill_tick").cast(pl.Float64, strict=False),
        pl.col("rt_ticks").cast(pl.Float64, strict=False),
        pl.col("distance").cast(pl.Float64, strict=False),
        pl.col("round_num").cast(pl.Int64, strict=False),
        pl.col("headshot").cast(pl.Boolean, strict=False).fill_null(False),
        pl.col("is_thrusmoke").cast(pl.Boolean, strict=False).fill_null(False),
        pl.col("is_micropeek_4").cast(pl.Boolean, strict=False).fill_null(False),
    ).sort(key_cols + ["kill_tick"])

    weapon_family_expr = (
        pl.when(pl.col("weapon").str.to_lowercase().is_in(["ak47", "m4a1", "m4a1_silencer", "famas", "galilar", "aug", "sg556"]))
        .then(pl.lit("rifle"))
        .when(pl.col("weapon").str.to_lowercase().is_in(["glock", "hkp2000", "usp_silencer", "p250", "elite", "fiveseven", "tec9", "cz75a", "deagle", "revolver"]))
        .then(pl.lit("pistol"))
        .when(pl.col("weapon").str.to_lowercase().is_in(["awp", "ssg08", "mac10", "mp9", "mp7", "mp5sd", "ump45", "p90", "bizon"]))
        .then(pl.lit("awp_smg"))
        .otherwise(pl.lit("other"))
    )

    kills = all_kills.with_columns(
        weapon_family_expr.alias("weapon_family"),
        (pl.col("rt_ticks") <= -2).fill_null(False).alias("prefire_b"),
        (pl.col("is_thrusmoke")).fill_null(False).alias("thrusmoke_b"),
        (pl.col("headshot")).fill_null(False).alias("headshot_b"),
        (pl.col("rt_ticks") <= FAST_RT_TICKS).fill_null(False).alias("fast_rt_b"),
        (pl.col("rt_ticks") <= 2).fill_null(False).alias("rt_le_2_b"),
        (pl.col("rt_ticks") <= 4).fill_null(False).alias("rt_le_4_b"),
        ((pl.col("distance") >= LONG_RANGE_DIST) & pl.col("rt_ticks").is_not_null()).fill_null(False).alias("long_range_b"),
    ).with_columns(
        (pl.col("long_range_b") & pl.col("fast_rt_b")).alias("long_fast_b"),
        (pl.col("long_range_b") & pl.col("rt_le_4_b")).alias("long_fast_4_b"),
        (pl.col("prefire_b") & (pl.col("distance") >= LONG_RANGE_DIST).fill_null(False)).alias("prefire_long_range_b"),
    ).with_columns(
        (pl.col("prefire_b") | pl.col("thrusmoke_b") | pl.col("long_fast_4_b") | pl.col("is_micropeek_4")).alias("signal_b")
    )

    primary_agg = kills.group_by(key_cols, maintain_order=True).agg(
        pl.len().alias("n_kills"),
        pl.col("rt_ticks").drop_nulls().len().alias("n_kills_with_rt"),
        pl.col("rt_ticks").drop_nulls().len().alias("rt_n"),
        pl.col("round_num").drop_nulls().n_unique().alias("rounds_played"),
        pl.col("victim_steamid").n_unique().alias("n_victims"),
        pl.col("rt_ticks").drop_nulls().mean().alias("rt_mean"),
        pl.col("rt_ticks").drop_nulls().median().alias("rt_median"),
        pl.col("rt_ticks").drop_nulls().quantile(0.10, interpolation="nearest").alias("rt_p10"),
        pl.col("rt_ticks").drop_nulls().quantile(0.90, interpolation="nearest").alias("rt_p90"),
        pl.col("rt_ticks").drop_nulls().std(ddof=1).alias("rt_std"),
        pl.col("distance").mean().alias("dist_mean"),
        pl.col("distance").median().alias("dist_median"),
        pl.col("distance").quantile(0.90, interpolation="nearest").alias("dist_p90"),
        pl.col("weapon").n_unique().alias("weapon_n_unique"),
        pl.col("headshot_b").sum().cast(pl.Int64).alias("headshot_count"),
        pl.col("fast_rt_b").sum().cast(pl.Int64).alias("fast_rt_count"),
        pl.col("rt_le_2_b").sum().cast(pl.Int64).alias("rt_le_2_count"),
        pl.col("rt_le_4_b").sum().cast(pl.Int64).alias("rt_le_4_count"),
        pl.col("prefire_b").sum().cast(pl.Int64).alias("prefire_count"),
        pl.col("prefire_long_range_b").sum().cast(pl.Int64).alias("prefire_long_range_count"),
        pl.col("victim_steamid").filter(pl.col("prefire_b")).n_unique().alias("prefire_victim_n"),
        pl.col("thrusmoke_b").sum().cast(pl.Int64).alias("thrusmoke_kills"),
        pl.col("round_num").filter(pl.col("thrusmoke_b")).drop_nulls().n_unique().alias("thrusmoke_rounds"),
        pl.col("long_range_b").sum().cast(pl.Int64).alias("long_range_kills_with_rt"),
        pl.col("long_fast_b").sum().cast(pl.Int64).alias("long_range_fast_rt_count"),
        pl.col("long_fast_4_b").sum().cast(pl.Int64).alias("long_range_fast_rt_4_count"),
        pl.col("thrusmoke_b").cast(pl.Int8).alias("thrusmoke_seq"),
        pl.col("headshot_b").cast(pl.Int8).alias("headshot_seq"),
        pl.col("prefire_b").cast(pl.Int8).alias("prefire_seq"),
        pl.col("rt_le_4_b").cast(pl.Int8).alias("fast_rt_seq"),
        (pl.col("weapon_family") == "rifle").sum().cast(pl.Int64).alias("rifle_kills"),
        (pl.col("weapon_family") == "pistol").sum().cast(pl.Int64).alias("pistol_kills"),
        (pl.col("weapon_family") == "awp_smg").sum().cast(pl.Int64).alias("awp_smg_kills"),
        ((pl.col("weapon_family") == "rifle") & pl.col("fast_rt_b")).sum().cast(pl.Int64).alias("rifle_fast_rt_count"),
        ((pl.col("weapon_family") == "pistol") & pl.col("fast_rt_b")).sum().cast(pl.Int64).alias("pistol_fast_rt_count"),
        ((pl.col("weapon_family") == "awp_smg") & pl.col("fast_rt_b")).sum().cast(pl.Int64).alias("awp_smg_fast_rt_count"),
        ((pl.col("weapon_family") == "rifle") & pl.col("prefire_b")).sum().cast(pl.Int64).alias("rifle_prefire_count"),
        ((pl.col("weapon_family") == "pistol") & pl.col("prefire_b")).sum().cast(pl.Int64).alias("pistol_prefire_count"),
        ((pl.col("weapon_family") == "awp_smg") & pl.col("prefire_b")).sum().cast(pl.Int64).alias("awp_smg_prefire_count"),
        ((pl.col("weapon_family") == "rifle") & pl.col("thrusmoke_b")).sum().cast(pl.Int64).alias("rifle_thrusmoke_count"),
        ((pl.col("weapon_family") == "pistol") & pl.col("thrusmoke_b")).sum().cast(pl.Int64).alias("pistol_thrusmoke_count"),
        ((pl.col("weapon_family") == "awp_smg") & pl.col("thrusmoke_b")).sum().cast(pl.Int64).alias("awp_smg_thrusmoke_count"),
    ).with_columns(
        pl.col("thrusmoke_seq").map_elements(lambda seq: longest_true_streak(_list_to_bools(seq)), return_dtype=pl.Int64).alias("max_thrusmoke_streak"),
        pl.col("headshot_seq").map_elements(lambda seq: longest_true_streak(_list_to_bools(seq)), return_dtype=pl.Int64).alias("max_headshot_streak"),
        pl.col("prefire_seq").map_elements(lambda seq: longest_true_streak(_list_to_bools(seq)), return_dtype=pl.Int64).alias("max_prefire_streak"),
        pl.col("fast_rt_seq").map_elements(lambda seq: longest_true_streak(_list_to_bools(seq)), return_dtype=pl.Int64).alias("max_fast_rt_streak"),
    ).drop(["thrusmoke_seq", "headshot_seq", "prefire_seq", "fast_rt_seq"])

    round_counts = kills.drop_nulls("round_num").group_by(key_cols + ["round_num"], maintain_order=True).agg(pl.len().alias("round_kills"))
    round_agg = round_counts.group_by(key_cols, maintain_order=True).agg(
        pl.len().alias("rounds_with_kills"),
        pl.col("round_kills").max().alias("max_round_kills"),
        pl.col("round_kills").alias("round_count_list"),
        (pl.col("round_kills") >= 2).sum().cast(pl.Int64).alias("multi_kill_rounds"),
    ).with_columns(
        (pl.col("max_round_kills") / pl.col("round_count_list").list.sum()).alias("top_round_kill_share"),
        pl.col("round_count_list").map_elements(normalized_entropy_from_list, return_dtype=pl.Float64).alias("round_kill_entropy"),
    ).drop(["max_round_kills", "round_count_list"])

    thr_round_counts = kills.filter(pl.col("thrusmoke_b")).drop_nulls("round_num").group_by(key_cols + ["round_num"], maintain_order=True).agg(pl.len().alias("thr_round_hits"))
    thr_round_agg = thr_round_counts.group_by(key_cols, maintain_order=True).agg(
        (pl.col("thr_round_hits") >= 2).sum().cast(pl.Int64).alias("thrusmoke_repeat_rounds"),
        pl.col("round_num").alias("thr_round_list"),
    ).with_columns(
        pl.col("thr_round_list").map_elements(lambda vals: longest_consecutive_int_streak(_list_to_ints(vals)), return_dtype=pl.Int64).alias("max_thrusmoke_round_streak")
    ).drop("thr_round_list")

    signal_round_counts = kills.filter(pl.col("signal_b")).drop_nulls("round_num").group_by(key_cols + ["round_num"], maintain_order=True).agg(pl.len().alias("signal_round_hits"))
    signal_agg = signal_round_counts.group_by(key_cols, maintain_order=True).agg(
        pl.col("signal_round_hits").max().alias("max_signal_round_hits"),
        pl.col("signal_round_hits").alias("signal_round_list"),
    ).with_columns(
        (pl.col("max_signal_round_hits") / pl.col("signal_round_list").list.sum()).fill_nan(0.0).fill_null(0.0).alias("top_signal_round_share"),
        pl.col("signal_round_list").map_elements(normalized_entropy_from_list, return_dtype=pl.Float64).alias("signal_round_entropy"),
    ).drop(["max_signal_round_hits", "signal_round_list"])

    weapon_counts = kills.group_by(key_cols + ["weapon_family"], maintain_order=True).agg(pl.len().alias("weapon_family_count"))
    weapon_agg = weapon_counts.group_by(key_cols, maintain_order=True).agg(
        (pl.col("weapon_family_count").max() / pl.col("weapon_family_count").sum()).alias("dominant_weapon_share"),
        pl.col("weapon_family_count").alias("weapon_count_list"),
    ).with_columns(
        pl.col("weapon_count_list").map_elements(normalized_entropy_from_list, return_dtype=pl.Float64).alias("weapon_entropy")
    ).drop("weapon_count_list")

    victim_counts = kills.group_by(key_cols + ["victim_steamid"], maintain_order=True).agg(pl.len().alias("victim_count"))
    victim_agg = victim_counts.group_by(key_cols, maintain_order=True).agg(
        (pl.col("victim_count").max() / pl.col("victim_count").sum()).alias("top_victim_share"),
        pl.col("victim_count").alias("victim_count_list"),
    ).with_columns(
        pl.col("victim_count_list").map_elements(normalized_entropy_from_list, return_dtype=pl.Float64).alias("victim_entropy")
    ).drop("victim_count_list")

    agg_pl = primary_agg.join(round_agg, on=key_cols, how="left")
    agg_pl = agg_pl.join(thr_round_agg, on=key_cols, how="left")
    agg_pl = agg_pl.join(signal_agg, on=key_cols, how="left")
    agg_pl = agg_pl.join(weapon_agg, on=key_cols, how="left")
    agg_pl = agg_pl.join(victim_agg, on=key_cols, how="left")
    agg_pl = agg_pl.with_columns(
        pl.col("thrusmoke_repeat_rounds").fill_null(0),
        pl.col("max_thrusmoke_round_streak").fill_null(0),
        pl.col("top_signal_round_share").fill_null(0.0),
        pl.col("signal_round_entropy").fill_null(0.0),
        (pl.col("n_kills") / pl.when(pl.col("rounds_with_kills") > 0).then(pl.col("rounds_with_kills")).otherwise(1)).alias("kill_density"),
        pl.col("n_kills").alias("hs_n"),
        pl.col("n_kills").alias("smoke_n"),
    )

    all_encounters = pl.DataFrame() if encounter_df is None else (pl.from_pandas(encounter_df) if isinstance(encounter_df, pd.DataFrame) else encounter_df)
    if not all_encounters.is_empty():
        all_encounters = all_encounters.with_columns(
            pl.col("demo_id").cast(pl.Utf8),
            pl.col("map_name").cast(pl.Utf8),
            pl.col("attacker_steamid").cast(pl.Utf8).str.strip_chars(),
            pl.col("attacker_name").cast(pl.Utf8),
            pl.col("label").cast(pl.Int64),
        )
        enc_exprs: list[pl.Expr] = [pl.len().alias("enc_n")]
        for source_col, cfg in ENCOUNTER_FEATURE_SPECS.items():
            if source_col not in all_encounters.columns:
                continue
            col = pl.col(source_col).cast(pl.Float64, strict=False)
            prefix = cfg["prefix"]
            enc_exprs.extend(
                [
                    col.mean().alias(f"{prefix}_mean"),
                    col.median().alias(f"{prefix}_median"),
                    col.quantile(0.10, interpolation="nearest").alias(f"{prefix}_p10"),
                    col.quantile(0.90, interpolation="nearest").alias(f"{prefix}_p90"),
                    col.std(ddof=1).alias(f"{prefix}_std"),
                ]
            )
            low = cfg.get("low")
            high = cfg.get("high")
            if low is not None:
                enc_exprs.append(((((col <= low).sum()) + LAPLACE_ALPHA) / (pl.len() + (2.0 * LAPLACE_ALPHA))).alias(f"{prefix}_low_rate"))
            if high is not None:
                enc_exprs.append(((((col >= high).sum()) + LAPLACE_ALPHA) / (pl.len() + (2.0 * LAPLACE_ALPHA))).alias(f"{prefix}_high_rate"))

        if "ended_in_kill_within_y" in all_encounters.columns:
            enc_exprs.append(((((pl.col("ended_in_kill_within_y").cast(pl.Int64).sum()) + LAPLACE_ALPHA) / (pl.len() + (2.0 * LAPLACE_ALPHA))).alias("enc_kill_end_rate")))
        if "ended_in_damage" in all_encounters.columns:
            enc_exprs.append(((((pl.col("ended_in_damage").cast(pl.Int64).sum()) + LAPLACE_ALPHA) / (pl.len() + (2.0 * LAPLACE_ALPHA))).alias("enc_damage_end_rate")))
        if "shot_before_aim_acquire" in all_encounters.columns:
            enc_exprs.append(((((pl.col("shot_before_aim_acquire").cast(pl.Int64).sum()) + LAPLACE_ALPHA) / (pl.len() + (2.0 * LAPLACE_ALPHA))).alias("enc_shot_before_acquire_rate")))
        if "damage_count" in all_encounters.columns:
            dmg_count = pl.col("damage_count").cast(pl.Float64, strict=False)
            enc_exprs.append((((((dmg_count >= 2).sum()) + LAPLACE_ALPHA) / (pl.len() + (2.0 * LAPLACE_ALPHA))).alias("enc_multi_damage_rate")))

        enc_agg = all_encounters.group_by(key_cols, maintain_order=True).agg(enc_exprs)
        if "attacker_side" in all_encounters.columns:
            side_agg = all_encounters.with_columns(
                pl.col("attacker_side").cast(pl.Utf8).str.to_lowercase().str.strip_chars()
            ).group_by(key_cols, maintain_order=True).agg(
                (pl.col("attacker_side") == "ct").sum().cast(pl.Float64).alias("enc_ct_n"),
                (pl.col("attacker_side") == "t").sum().cast(pl.Float64).alias("enc_t_n"),
            ).with_columns(
                (pl.min_horizontal("enc_ct_n", "enc_t_n") / pl.max_horizontal("enc_ct_n", "enc_t_n")).alias("enc_side_balance")
            )
            enc_agg = enc_agg.join(side_agg, on=key_cols, how="left")
        agg_pl = agg_pl.join(enc_agg, on=key_cols, how="left")

    agg = agg_pl.to_pandas()

    if encounter_df is not None:
        encounter_pdf = encounter_df.to_pandas() if isinstance(encounter_df, pl.DataFrame) else encounter_df
        if encounter_pdf is not None and not encounter_pdf.empty:
            encounter_pdf = encounter_pdf.copy()
            for col, default in [
                ("demo_id", ""),
                ("map_name", ""),
                ("attacker_steamid", ""),
                ("attacker_name", ""),
                ("label", -1),
                ("visible_ratio", np.nan),
                ("aim_error_min", np.nan),
                ("aim_acquire_time", np.nan),
                ("pre_shot_aim_error_mean", np.nan),
                ("post_acquire_error_std", np.nan),
                ("relative_speed_mean", np.nan),
                ("attacker_speed_mean", np.nan),
                ("victim_speed_mean", np.nan),
                ("distance_mean", np.nan),
                ("ended_in_kill_within_y", False),
            ]:
                if col not in encounter_pdf.columns:
                    encounter_pdf[col] = default
            encounter_pdf["attacker_steamid"] = encounter_pdf["attacker_steamid"].astype(str).str.strip()
            joint_rows = [build_encounter_row(g) for _, g in encounter_pdf.groupby(key_cols, sort=False)]
            joint_df = pd.DataFrame(joint_rows)
            if not joint_df.empty:
                keep_cols = key_cols + [
                    "enc_hard_n",
                    "enc_easy_n",
                    "enc_hard_low_error_rate",
                    "enc_hard_fast_acquire_rate",
                    "enc_hard_clean_preshot_rate",
                    "enc_hard_low_noise_rate",
                    "enc_hard_finish_rate",
                    "enc_easy_low_error_rate",
                    "enc_precision_under_difficulty",
                    "enc_difficulty_precision_gap",
                ]
                joint_df = joint_df[[c for c in keep_cols if c in joint_df.columns]]
                agg = agg.merge(joint_df, on=key_cols, how="left")
    agg["dataset_source"] = agg["demo_id"].map(source_of_demo_id)

    before_min_kills = int(len(agg))
    agg = agg[agg["n_kills_with_rt"] >= MIN_KILLS].copy()

    n_players = (
        all_kills.group_by("demo_id")
        .agg(pl.col("attacker_steamid").n_unique().alias("n_players"))
        .to_pandas()
    )
    agg = agg.merge(n_players, on="demo_id", how="left")
    agg["kills_per_player"] = agg["n_kills"] / agg["n_players"].replace(0, np.nan)

    agg["fast_rt_rate"] = [laplace(s, n) for s, n in zip(agg["fast_rt_count"], agg["rt_n"])]
    agg["headshot_rate"] = [laplace(s, n) for s, n in zip(agg["headshot_count"], agg["hs_n"])]
    agg["rt_le_2_rate"] = [laplace(s, n) for s, n in zip(agg["rt_le_2_count"], agg["rt_n"])]
    agg["rt_le_4_rate"] = [laplace(s, n) for s, n in zip(agg["rt_le_4_count"], agg["rt_n"])]
    agg["prefire_rate"] = [laplace(s, n) for s, n in zip(agg["prefire_count"], agg["n_kills"])]
    agg["prefire_long_range_rate"] = [laplace(s, n) for s, n in zip(agg["prefire_long_range_count"], agg["n_kills"])]
    agg["prefire_repeat_victims"] = [laplace(s, n) for s, n in zip(agg["prefire_victim_n"], agg["n_victims"])]
    agg["thrusmoke_kill_rate"] = [laplace(s, n) for s, n in zip(agg["thrusmoke_kills"], agg["n_kills"])]
    agg["thrusmoke_round_rate"] = [laplace(s, n) for s, n in zip(agg["thrusmoke_rounds"], agg["rounds_played"])]
    agg["long_range_fast_rt_rate"] = [laplace(s, n) for s, n in zip(agg["long_range_fast_rt_count"], agg["long_range_kills_with_rt"])]
    agg["long_range_fast_rt_rate_4"] = [laplace(s, n) for s, n in zip(agg["long_range_fast_rt_4_count"], agg["long_range_kills_with_rt"])]

    agg["rifle_kill_share"] = [laplace(s, n) for s, n in zip(agg["rifle_kills"], agg["n_kills"])]
    agg["pistol_kill_share"] = [laplace(s, n) for s, n in zip(agg["pistol_kills"], agg["n_kills"])]
    agg["awp_smg_kill_share"] = [laplace(s, n) for s, n in zip(agg["awp_smg_kills"], agg["n_kills"])]

    agg["rifle_fast_rt_rate"] = [laplace(s, n) for s, n in zip(agg["rifle_fast_rt_count"], agg["rifle_kills"])]
    agg["pistol_fast_rt_rate"] = [laplace(s, n) for s, n in zip(agg["pistol_fast_rt_count"], agg["pistol_kills"])]
    agg["awp_smg_fast_rt_rate"] = [laplace(s, n) for s, n in zip(agg["awp_smg_fast_rt_count"], agg["awp_smg_kills"])]

    agg["prefire_rate_rifle"] = [laplace(s, n) for s, n in zip(agg["rifle_prefire_count"], agg["rifle_kills"])]
    agg["prefire_rate_pistol"] = [laplace(s, n) for s, n in zip(agg["pistol_prefire_count"], agg["pistol_kills"])]
    agg["prefire_rate_awp_smg"] = [laplace(s, n) for s, n in zip(agg["awp_smg_prefire_count"], agg["awp_smg_kills"])]

    agg["thrusmoke_rate_rifle"] = [laplace(s, n) for s, n in zip(agg["rifle_thrusmoke_count"], agg["rifle_kills"])]
    agg["thrusmoke_rate_pistol"] = [laplace(s, n) for s, n in zip(agg["pistol_thrusmoke_count"], agg["pistol_kills"])]
    agg["thrusmoke_rate_awp_smg"] = [laplace(s, n) for s, n in zip(agg["awp_smg_thrusmoke_count"], agg["awp_smg_kills"])]

    agg["prefire_rate_w"] = agg["prefire_rate"] * np.log1p(agg["rt_n"])
    agg["thrusmoke_rate_w"] = agg["thrusmoke_kill_rate"] * np.log1p(agg["n_kills"])
    agg["fast_rt_rate_w"] = agg["fast_rt_rate"] * np.log1p(agg["rt_n"])

    if "enc_kill_end_rate" in agg.columns and "enc_visible_ratio_low_rate" in agg.columns:
        agg["enc_low_vis_kill_pressure"] = agg["enc_kill_end_rate"].fillna(0.0) * agg["enc_visible_ratio_low_rate"].fillna(0.0)
    if "enc_shot_before_acquire_rate" in agg.columns and "enc_visible_ratio_low_rate" in agg.columns:
        agg["enc_low_vis_preacquire_pressure"] = agg["enc_shot_before_acquire_rate"].fillna(0.0) * agg["enc_visible_ratio_low_rate"].fillna(0.0)
    if "enc_kill_end_rate" in agg.columns and "enc_visible_ratio_low_rate" in agg.columns:
        base = agg["enc_kill_end_rate"].replace(0, np.nan)
        agg["enc_low_vis_precision_retention"] = (agg.get("enc_low_vis_kill_pressure", 0.0) / base).clip(lower=0.0, upper=1.5)
    if "enc_aim_acquire_low_rate" in agg.columns and "enc_aim_error_min_low_rate" in agg.columns:
        agg["enc_process_abnormality"] = (
            agg["enc_aim_acquire_low_rate"].fillna(0.0) * 0.24
            + agg["enc_aim_error_min_low_rate"].fillna(0.0) * 0.22
            + agg.get("enc_shot_before_acquire_rate", 0.0) * 0.22
            + agg.get("enc_low_vis_precision_retention", 0.0) * 0.18
            + agg.get("enc_visible_ratio_low_rate", 0.0) * 0.14
        ).clip(lower=0.0, upper=1.5)
    if "enc_aim_collapse_rate_high_rate" in agg.columns and "enc_preshot_err_low_rate" in agg.columns:
        agg["enc_snap_process_score"] = (
            agg["enc_aim_collapse_rate_high_rate"].fillna(0.0) * 0.22
            + agg.get("enc_aim_collapse_ratio_high_rate", 0.0) * 0.18
            + agg.get("enc_preshot_err_low_rate", 0.0) * 0.16
            + agg.get("enc_preshot_err_std_low_rate", 0.0) * 0.12
            + agg.get("enc_snap_vel_early_high_rate", 0.0) * 0.12
            + agg.get("enc_snap_vel_shot_high_rate", 0.0) * 0.10
            + agg.get("enc_snap_jerk_early_high_rate", 0.0) * 0.05
            + agg.get("enc_snap_jerk_shot_high_rate", 0.0) * 0.05
        ).clip(lower=0.0, upper=1.5)
        agg["enc_low_noise_lock_score"] = (
            agg.get("enc_post_acquire_err_low_rate", 0.0).fillna(0.0) * 0.34
            + agg.get("enc_post_acquire_err_std_low_rate", 0.0).fillna(0.0) * 0.26
            + agg.get("enc_acquire_shot_lag_low_rate", 0.0).fillna(0.0) * 0.20
            + agg.get("enc_aim_flips_low_rate", 0.0).fillna(0.0) * 0.20
        ).clip(lower=0.0, upper=1.5)
        agg["aim_process_global_score"] = (
            agg.get("enc_process_abnormality", 0.0).fillna(0.0) * 0.28
            + agg.get("enc_snap_process_score", 0.0).fillna(0.0) * 0.42
            + agg.get("enc_low_noise_lock_score", 0.0).fillna(0.0) * 0.30
        ).clip(lower=0.0, upper=1.5)
    if "enc_mouse_burst_high_rate" in agg.columns:
        agg["enc_input_burst_score"] = (
            agg.get("enc_mouse_burst_high_rate", 0.0).fillna(0.0) * 0.34
            + agg.get("enc_mouse_delta_p90_high_rate", 0.0).fillna(0.0) * 0.18
            + agg.get("enc_mouse_delta_max_high_rate", 0.0).fillna(0.0) * 0.16
            + agg.get("enc_mouse_dx_flip_low_rate", 0.0).fillna(0.0) * 0.14
            + agg.get("enc_mouse_dy_flip_low_rate", 0.0).fillna(0.0) * 0.10
            + agg.get("enc_mouse_quiet_high_rate", 0.0).fillna(0.0) * 0.08
        ).clip(lower=0.0, upper=1.5)
        agg["enc_input_stability_score"] = (
            agg.get("enc_mouse_quiet_high_rate", 0.0).fillna(0.0) * 0.34
            + agg.get("enc_mouse_delta_std_low_rate", 0.0).fillna(0.0) * 0.24
            + agg.get("enc_mouse_dx_flip_low_rate", 0.0).fillna(0.0) * 0.16
            + agg.get("enc_mouse_dy_flip_low_rate", 0.0).fillna(0.0) * 0.16
            + agg.get("enc_hard_fast_acquire_rate", 0.0).fillna(0.0) * 0.10
        ).clip(lower=0.0, upper=1.5)
        base_aim_global = agg.get("aim_process_global_score", pd.Series(0.0, index=agg.index)).fillna(0.0)
        agg["aim_process_global_score"] = (
            base_aim_global * 0.72
            + agg.get("enc_input_burst_score", 0.0).fillna(0.0) * 0.16
            + agg.get("enc_input_stability_score", 0.0).fillna(0.0) * 0.12
        ).clip(lower=0.0, upper=1.5)
    if "top_signal_round_share" in agg.columns and "dominant_weapon_share" in agg.columns:
        agg["selective_activation_score"] = (
            agg["top_signal_round_share"].fillna(0.0) * 0.34
            + agg["dominant_weapon_share"].fillna(0.0) * 0.22
            + agg["top_round_kill_share"].fillna(0.0) * 0.20
            + agg.get("late_signal_share", pd.Series(0.0, index=agg.index)).fillna(0.0) * 0.14
            + agg.get("late_round_kill_share", pd.Series(0.0, index=agg.index)).fillna(0.0) * 0.10
        ).clip(lower=0.0, upper=1.0)

    agg["rt_iqr_80"] = agg["rt_p90"] - agg["rt_p10"]
    agg["dist_tail"] = agg["dist_p90"] - agg["dist_median"]

    global_rt_median = float(agg["rt_median"].median(skipna=True))
    global_rt_p10 = float(agg["rt_p10"].median(skipna=True))
    global_rt_p90 = float(agg["rt_p90"].median(skipna=True))
    global_dist_median = float(agg["dist_median"].median(skipna=True))

    agg["rt_median_shrunk"] = (agg["rt_median"] * agg["rt_n"] + global_rt_median * SHRINK_K) / (agg["rt_n"] + SHRINK_K)
    agg["rt_p10_shrunk"] = (agg["rt_p10"] * agg["rt_n"] + global_rt_p10 * SHRINK_K) / (agg["rt_n"] + SHRINK_K)
    agg["rt_p90_shrunk"] = (agg["rt_p90"] * agg["rt_n"] + global_rt_p90 * SHRINK_K) / (agg["rt_n"] + SHRINK_K)
    agg["dist_median_shrunk"] = (agg["dist_median"] * agg["n_kills"] + global_dist_median * SHRINK_K) / (agg["n_kills"] + SHRINK_K)

    rt_derived = [
        "rt_mean",
        "rt_median",
        "rt_p10",
        "rt_p90",
        "rt_std",
        "rt_median_shrunk",
        "rt_p10_shrunk",
        "rt_p90_shrunk",
        "fast_rt_rate",
        "fast_rt_rate_w",
        "rt_le_2_rate",
        "rt_le_4_rate",
        "prefire_rate",
        "prefire_rate_w",
        "prefire_long_range_rate",
        "prefire_repeat_victims",
        "long_range_fast_rt_rate",
        "long_range_fast_rt_rate_4",
        "max_fast_rt_streak",
        "max_prefire_streak",
        "rifle_fast_rt_rate",
        "pistol_fast_rt_rate",
        "awp_smg_fast_rt_rate",
        "prefire_rate_rifle",
        "prefire_rate_pistol",
        "prefire_rate_awp_smg",
        "enc_low_vis_kill_pressure",
        "enc_low_vis_preacquire_pressure",
        "enc_low_vis_precision_retention",
        "enc_process_abnormality",
        "enc_snap_process_score",
        "enc_low_noise_lock_score",
        "aim_process_global_score",
        "selective_activation_score",
        "aim_assist_style_score",
        "trigger_timing_style_score",
        "information_assist_style_score",
        "mechanical_vs_surface_gap",
        "timing_vs_surface_gap",
        "info_vs_surface_gap",
    ]
    low_evidence = agg["rt_n"] < MIN_RT_EVIDENCE
    for c in rt_derived:
        if c in agg.columns:
            agg.loc[low_evidence, c] = np.nan

    norm_map = {
        "rt_median": ("rt_median_pct", "rt_median_z"),
        "prefire_rate": ("prefire_pct", "prefire_z"),
        "thrusmoke_kill_rate": ("thrusmoke_pct", "thrusmoke_z"),
        "headshot_rate": ("hs_pct", "hs_z"),
        "kill_density": ("kill_density_pct", "kill_density_z"),
        "prefire_long_range_rate": ("prefire_long_range_pct", "prefire_long_range_z"),
        "long_range_fast_rt_rate_4": ("long_fast_rt_pct", "long_fast_rt_z"),
        "max_thrusmoke_round_streak": ("max_thr_round_streak_pct", "max_thr_round_streak_z"),
        "dist_tail": ("dist_tail_pct", "dist_tail_z"),
        "enc_hard_finish_rate": ("enc_hard_finish_pct", "enc_hard_finish_z"),
        "enc_kill_end_rate": ("enc_kill_end_pct", "enc_kill_end_z"),
    }
    for base_col, (pct_col, z_col) in norm_map.items():
        if base_col in agg.columns:
            agg = add_demo_norms(agg, base_col, pct_col, z_col)

    aim_process = agg.get("aim_process_global_score", pd.Series(0.0, index=agg.index)).fillna(0.0)
    snap_process = agg.get("enc_snap_process_score", pd.Series(0.0, index=agg.index)).fillna(0.0)
    low_noise_lock = agg.get("enc_low_noise_lock_score", pd.Series(0.0, index=agg.index)).fillna(0.0)
    input_burst = agg.get("enc_input_burst_score", pd.Series(0.0, index=agg.index)).fillna(0.0)
    input_stability = agg.get("enc_input_stability_score", pd.Series(0.0, index=agg.index)).fillna(0.0)
    selective_activation = agg.get("selective_activation_score", pd.Series(0.0, index=agg.index)).fillna(0.0)
    trigger_speed = agg.get("rt_le_2_rate", pd.Series(0.0, index=agg.index)).fillna(0.0)
    trigger_window = agg.get("rt_le_4_rate", pd.Series(0.0, index=agg.index)).fillna(0.0)
    ttfshot_low = agg.get("enc_ttfshot_low_rate", pd.Series(0.0, index=agg.index)).fillna(0.0)
    acquire_shot_low = agg.get("enc_acquire_shot_lag_low_rate", pd.Series(0.0, index=agg.index)).fillna(0.0)
    shot_before_acquire = agg.get("enc_shot_before_acquire_rate", pd.Series(0.0, index=agg.index)).fillna(0.0)
    aim_min_tick_low = agg.get("enc_aim_min_tick_low_rate", pd.Series(0.0, index=agg.index)).fillna(0.0)
    hard_fast_acquire = agg.get("enc_hard_fast_acquire_rate", pd.Series(0.0, index=agg.index)).fillna(0.0)
    prefire_pct = agg.get("prefire_pct", pd.Series(0.0, index=agg.index)).fillna(0.0)
    prefire_long_pct = agg.get("prefire_long_range_pct", pd.Series(0.0, index=agg.index)).fillna(0.0)
    thrusmoke_pct = agg.get("thrusmoke_pct", pd.Series(0.0, index=agg.index)).fillna(0.0)
    low_vis_retention = agg.get("enc_low_vis_precision_retention", pd.Series(0.0, index=agg.index)).fillna(0.0)
    low_vis_pressure = agg.get("enc_low_vis_kill_pressure", pd.Series(0.0, index=agg.index)).fillna(0.0)
    low_vis_preacquire = agg.get("enc_low_vis_preacquire_pressure", pd.Series(0.0, index=agg.index)).fillna(0.0)
    low_vis_rate = agg.get("enc_visible_ratio_low_rate", pd.Series(0.0, index=agg.index)).fillna(0.0)
    kill_density_pct = agg.get("kill_density_pct", pd.Series(0.0, index=agg.index)).fillna(0.0)
    hs_pct = agg.get("hs_pct", pd.Series(0.0, index=agg.index)).fillna(0.0)
    long_fast_pct = agg.get("long_fast_rt_pct", pd.Series(0.0, index=agg.index)).fillna(0.0)

    agg["aim_assist_style_score"] = (
        aim_process * 0.46
        + snap_process * 0.20
        + low_noise_lock * 0.16
        + input_burst * 0.10
        + input_stability * 0.08
    ).clip(lower=0.0, upper=1.5)
    agg["trigger_timing_style_score"] = (
        trigger_speed * 0.18
        + trigger_window * 0.12
        + ttfshot_low * 0.18
        + acquire_shot_low * 0.18
        + shot_before_acquire * 0.14
        + aim_min_tick_low * 0.08
        + hard_fast_acquire * 0.06
        + selective_activation * 0.06
    ).clip(lower=0.0, upper=1.5)
    agg["information_assist_style_score"] = (
        prefire_pct * 0.20
        + prefire_long_pct * 0.12
        + thrusmoke_pct * 0.10
        + low_vis_retention * 0.20
        + low_vis_pressure * 0.14
        + low_vis_preacquire * 0.12
        + low_vis_rate * 0.06
        + selective_activation * 0.06
    ).clip(lower=0.0, upper=1.5)
    agg["mechanical_vs_surface_gap"] = (
        agg["aim_assist_style_score"].fillna(0.0)
        - (0.58 * hs_pct + 0.42 * kill_density_pct)
    ).clip(lower=-1.5, upper=1.5)
    agg["timing_vs_surface_gap"] = (
        agg["trigger_timing_style_score"].fillna(0.0)
        - (0.55 * long_fast_pct + 0.45 * kill_density_pct)
    ).clip(lower=-1.5, upper=1.5)
    agg["info_vs_surface_gap"] = (
        agg["information_assist_style_score"].fillna(0.0)
        - (0.65 * kill_density_pct + 0.35 * hs_pct)
    ).clip(lower=-1.5, upper=1.5)

    helper_cols = [
        "headshot_count",
        "fast_rt_count",
        "rt_le_2_count",
        "rt_le_4_count",
        "prefire_count",
        "prefire_long_range_count",
        "prefire_victim_n",
        "long_range_fast_rt_count",
        "long_range_fast_rt_4_count",
        "rifle_fast_rt_count",
        "pistol_fast_rt_count",
        "awp_smg_fast_rt_count",
        "rifle_prefire_count",
        "pistol_prefire_count",
        "awp_smg_prefire_count",
        "rifle_thrusmoke_count",
        "pistol_thrusmoke_count",
        "awp_smg_thrusmoke_count",
    ]
    agg = agg.drop(columns=[c for c in helper_cols if c in agg.columns])
    agg.attrs["player_rows_before_min_kills"] = before_min_kills
    return agg


def add_demo_norms(df: pd.DataFrame, base_col: str, pct_col: str, z_col: str) -> pd.DataFrame:
    grp = df.groupby("demo_id")[base_col]
    mean = grp.transform("mean")
    std = grp.transform("std")
    rank = grp.rank(method="average", pct=True)
    df[pct_col] = rank
    df[z_col] = (df[base_col] - mean) / std.replace(0, np.nan)
    return df


def main():
    args = parse_args()
    train_mode = resolve_train_data_mode(args.train_data)
    out_path = player_features_path(PROCESSED_ROOT, train_mode)
    summary_path = player_features_summary_path(PROCESSED_ROOT, train_mode)
    cheater_map = load_cheater_map(CHEATER_CSV)

    files = sorted(IN_ROOT.glob(r"*/engagement_features.parquet"))
    encounter_files = sorted(IN_ROOT.glob(r"*/encounters.parquet"))
    if not files:
        raise FileNotFoundError(f"No engagement_features.parquet found under {IN_ROOT}")

    print(f"[INFO] found {len(files)} engagement files")
    print(f"[INFO] found {len(encounter_files)} encounter files")

    dfs: list[pl.DataFrame] = []
    encounter_dfs: list[pl.DataFrame] = []
    source_counts = {
        "local_awpy": {"demos": set(), "kill_rows": 0, "encounter_rows": 0},
        "cs2cd": {"demos": set(), "kill_rows": 0, "encounter_rows": 0},
    }
    for f in files:
        demo_id = f.parent.name
        source = source_of_demo_id(demo_id)
        if train_mode == "local" and source != "local_awpy":
            continue
        if train_mode == "cs2cd" and source != "cs2cd":
            continue
        if source not in source_counts:
            continue
        raw_df = pl.read_parquet(f)
        df = label_demo_frame_pl(raw_df, demo_id, source, cheater_map)
        if df is None:
            continue
        df = ensure_columns_pl(df, [
            ("rt_ticks", np.nan),
            ("distance", np.nan),
            ("headshot", False),
            ("is_thrusmoke", False),
            ("round_num", np.nan),
            ("kill_tick", np.nan),
            ("victim_steamid", ""),
            ("weapon", ""),
            ("is_micropeek_4", False),
        ])

        dfs.append(df)
        source_counts[source]["demos"].add(demo_id)
        source_counts[source]["kill_rows"] += int(df.height)

    for f in encounter_files:
        demo_id = f.parent.name
        source = source_of_demo_id(demo_id)
        if train_mode == "local" and source != "local_awpy":
            continue
        if train_mode == "cs2cd" and source != "cs2cd":
            continue
        if source not in source_counts:
            continue

        raw_df = pl.read_parquet(f)
        df = label_demo_frame_pl(raw_df, demo_id, source, cheater_map)
        if df is None:
            continue
        df = ensure_columns_pl(df, [
            ("start_tick", np.nan),
            ("exposure_duration", np.nan),
            ("visible_ratio", np.nan),
            ("time_to_first_shot", np.nan),
            ("time_to_first_damage", np.nan),
            ("aim_error_at_first_visible", np.nan),
            ("aim_error_min", np.nan),
            ("aim_acquire_time", np.nan),
            ("aim_dwell_ticks", np.nan),
            ("aim_error_range", np.nan),
            ("aim_error_collapse_rate", np.nan),
            ("aim_error_collapse_ratio", np.nan),
            ("aim_error_min_tick_offset", np.nan),
            ("aim_correction_flips", np.nan),
            ("post_acquire_error_mean", np.nan),
            ("post_acquire_error_std", np.nan),
            ("pre_shot_aim_error_mean", np.nan),
            ("pre_shot_aim_error_std", np.nan),
            ("acquire_to_shot_lag", np.nan),
            ("snap_velocity_early_max", np.nan),
            ("snap_velocity_to_shot_max", np.nan),
            ("snap_jerk_early_max", np.nan),
            ("snap_jerk_to_shot_max", np.nan),
            ("shot_before_aim_acquire", False),
            ("shot_count", np.nan),
            ("shot_rate_per_128", np.nan),
            ("mean_shot_gap", np.nan),
            ("damage_count", np.nan),
            ("damage_total", np.nan),
            ("ended_in_damage", False),
            ("angular_velocity_mean", np.nan),
            ("angular_jerk_mean", np.nan),
            ("los_angular_velocity_mean", np.nan),
            ("los_angular_jerk_mean", np.nan),
            ("distance_mean", np.nan),
            ("closing_speed_mean", np.nan),
            ("attacker_speed_mean", np.nan),
            ("victim_speed_mean", np.nan),
            ("relative_speed_mean", np.nan),
            ("ended_in_kill_within_y", False),
            ("attacker_side", ""),
        ])
        encounter_dfs.append(df)
        source_counts[source]["encounter_rows"] += int(df.height)

    if not dfs:
        raise RuntimeError("No demos loaded after labeling. Check paths and CheaterSteamIDs.csv.")

    all_kills = pl.concat(dfs, how="diagonal_relaxed", rechunk=True)
    all_encounters = pl.concat(encounter_dfs, how="diagonal_relaxed", rechunk=True) if encounter_dfs else pl.DataFrame()
    print(f"[INFO] total kill rows: {all_kills.height}")
    print(f"[INFO] total encounter rows: {all_encounters.height}")

    agg = aggregate_kill_and_encounter_frames(all_kills, all_encounters)
    before_min_kills = int(agg.attrs.get("player_rows_before_min_kills", len(agg)))

    encounter_stack_path = encounter_player_feature_path(PROCESSED_ROOT, train_mode)
    encounter_manifest_path = PROCESSED_ROOT / "models" / f"encounter_nn_{train_mode}_training_manifest.json"
    use_encounter_stack = False
    if encounter_stack_path.exists() and encounter_manifest_path.exists():
        try:
            encounter_manifest = json.loads(encounter_manifest_path.read_text(encoding="utf-8"))
            use_encounter_stack = encounter_manifest.get("max_demos") in (None, "")
        except Exception:
            use_encounter_stack = False
    if use_encounter_stack:
        stacked = pd.read_parquet(encounter_stack_path)
        if not stacked.empty and {"demo_id", "attacker_steamid"}.issubset(stacked.columns):
            stacked = stacked.copy()
            stacked["demo_id"] = stacked["demo_id"].astype(str)
            stacked["attacker_steamid"] = stacked["attacker_steamid"].astype(str).str.strip()
            agg["demo_id"] = agg["demo_id"].astype(str)
            agg["attacker_steamid"] = agg["attacker_steamid"].astype(str).str.strip()
            agg = agg.merge(stacked, on=["demo_id", "attacker_steamid"], how="left")
            print(f"[INFO] merged encounter NN player features from {encounter_stack_path}")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.exists() and not OVERWRITE:
        raise FileExistsError(f"{out_path} exists and OVERWRITE=False")

    agg.to_parquet(out_path, index=False)
    print(f"[OK] wrote: {out_path}")
    print(f"[INFO] rows (player-demo): {len(agg)}")
    safe_print(f"[INFO] label counts:\n{agg.groupby('label').size()}")

    summary = {
        "train_data_mode": train_mode,
        "input_root": str(IN_ROOT),
        "output_path": str(out_path),
        "cheater_csv": str(CHEATER_CSV),
        "filters": {
            "MIN_KILLS": MIN_KILLS,
            "FAST_RT_TICKS": FAST_RT_TICKS,
            "MIN_RT_EVIDENCE": MIN_RT_EVIDENCE,
        },
        "source_stats": {
            src: {
                "loaded_demo_count": len(payload["demos"]),
                "loaded_kill_rows": int(payload["kill_rows"]),
                "loaded_encounter_rows": int(payload["encounter_rows"]),
            }
            for src, payload in source_counts.items()
        },
        "stage_row_counts": {
            "kill_rows_total_loaded": int(all_kills.height),
            "encounter_rows_total_loaded": int(all_encounters.height),
            "player_rows_before_min_kills": before_min_kills,
            "player_rows_after_min_kills": int(len(agg)),
        },
        "label_counts_after_min_kills": {
            "positive": int((agg["label"] == 1).sum()),
            "negative": int((agg["label"] == 0).sum()),
        },
    }
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"[OK] wrote: {summary_path}")


if __name__ == "__main__":
    main()

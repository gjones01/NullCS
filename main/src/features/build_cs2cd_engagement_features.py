from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import math
import os
from pathlib import Path
import sys
import traceback

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.adapters import cs2cd_adapter
from src.utils.project_paths import DEMOS_ROOT


OUT_ROOT = DEMOS_ROOT
W_PRE = 128
EYE_Z = 64.0
CHEST_Z = 56.0
ENCOUNTER_TIMEOUT_TICKS = 192
KILL_WITHIN_TICKS = 16
AIM_ACQUIRE_ERR_DEG = 5.0
WIDE_AIM_ERR_DEG = 20.0
MAX_FOV_ERR_DEG = 35.0


def wrap_deg(x: float) -> float:
    return ((float(x) + 180.0) % 360.0) - 180.0


def aim_error_deg(att_yaw: float, att_pitch: float, dx: float, dy: float, dz: float) -> float:
    tgt_yaw = math.degrees(math.atan2(dy, dx))
    horiz = math.hypot(dx, dy)
    tgt_pitch = -math.degrees(math.atan2(dz, horiz))
    dyaw = wrap_deg(tgt_yaw - att_yaw)
    dpitch = wrap_deg(tgt_pitch - att_pitch)
    return math.hypot(dyaw, dpitch)


def _quantile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    vals = sorted(float(v) for v in values)
    idx = min(len(vals) - 1, max(0, math.floor(q * (len(vals) - 1))))
    return float(vals[idx])


def _mean(values: list[float]) -> float | None:
    return float(sum(values) / len(values)) if values else None


def _std(values: list[float]) -> float | None:
    if len(values) < 2:
        return None
    mu = sum(values) / len(values)
    var = sum((v - mu) ** 2 for v in values) / (len(values) - 1)
    return float(math.sqrt(var))


def _count_direction_flips(values: list[float], tol: float = 1e-6) -> int:
    if len(values) < 3:
        return 0
    prev_sign = 0
    flips = 0
    for i in range(1, len(values)):
        delta = float(values[i]) - float(values[i - 1])
        if abs(delta) <= tol:
            continue
        sign = 1 if delta > 0 else -1
        if prev_sign and sign != prev_sign:
            flips += 1
        prev_sign = sign
    return flips


def _bool_series(values: pd.Series | object, index: pd.Index | None = None) -> pd.Series:
    if isinstance(values, pd.Series):
        s = values
    else:
        s = pd.Series(values if values is not None else False, index=index)
    if s.empty:
        return pd.Series(dtype=bool, index=index)
    if pd.api.types.is_bool_dtype(s):
        return s.fillna(False).astype(bool)
    lowered = s.astype("string").str.lower()
    return lowered.isin(["1", "true", "t", "yes", "y"])


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Build engagement and encounter features for CS2CD matches.")
    ap.add_argument("--max-matches", type=int, default=None, help="Maximum matches per split.")
    ap.add_argument("--overwrite", action="store_true", help="Overwrite existing outputs.")
    ap.add_argument("--workers", type=int, default=1, help="Parallel worker processes. Start with 2 on large runs.")
    return ap.parse_args()


def empty_encounters_df() -> pd.DataFrame:
    cols = [
        "demo_id",
        "map_name",
        "round_num",
        "encounter_id",
        "attacker_steamid",
        "attacker_name",
        "victim_steamid",
        "victim_name",
        "attacker_side",
        "victim_side",
        "start_tick",
        "end_tick",
        "exposure_duration",
        "visible_tick_count",
        "occluded_tick_count",
        "visible_ratio",
        "time_to_first_shot",
        "time_to_first_damage",
        "aim_error_at_first_visible",
        "aim_error_min",
        "aim_error_p10",
        "aim_error_p90",
        "aim_acquire_time",
        "aim_dwell_ticks",
        "aim_error_range",
        "aim_error_collapse_rate",
        "aim_error_collapse_ratio",
        "aim_error_min_tick_offset",
        "aim_correction_flips",
        "post_acquire_error_mean",
        "post_acquire_error_std",
        "pre_shot_aim_error_mean",
        "pre_shot_aim_error_std",
        "acquire_to_shot_lag",
        "snap_velocity_early_max",
        "snap_velocity_to_shot_max",
        "snap_jerk_early_max",
        "snap_jerk_to_shot_max",
        "mouse_delta_abs_mean",
        "mouse_delta_abs_p90",
        "mouse_delta_abs_max",
        "mouse_delta_abs_std",
        "mouse_dx_flip_rate",
        "mouse_dy_flip_rate",
        "pre_shot_mouse_burst_max",
        "post_acquire_mouse_quiet_rate",
        "walking_tick_rate",
        "airborne_tick_rate",
        "shot_before_aim_acquire",
        "shot_count",
        "shot_rate_per_128",
        "mean_shot_gap",
        "damage_count",
        "damage_total",
        "ended_in_damage",
        "ended_in_kill_within_y",
        "kill_tick",
        "weapon",
        "angular_velocity_mean",
        "angular_velocity_p90",
        "angular_velocity_max",
        "angular_velocity_std",
        "angular_jerk_mean",
        "angular_jerk_p90",
        "angular_jerk_max",
        "distance_mean",
        "distance_min",
        "distance_p90",
        "distance_max",
        "distance_std",
        "closing_speed_mean",
        "closing_speed_p90",
        "closing_speed_max",
        "attacker_speed_mean",
        "attacker_speed_p90",
        "victim_speed_mean",
        "victim_speed_p90",
        "relative_speed_mean",
        "relative_speed_p90",
        "los_angular_velocity_mean",
        "los_angular_velocity_p90",
        "los_angular_velocity_max",
        "los_angular_jerk_mean",
        "los_angular_jerk_p90",
        "los_angular_jerk_max",
        "damage_dir_delta_mean",
        "damage_dir_delta_p90",
        "penetration_count",
        "no_scope_damage_count",
        "in_air_damage_count",
    ]
    return pd.DataFrame(columns=cols)


def prepare_ticks(match: cs2cd_adapter.CS2CDMatch) -> pd.DataFrame:
    ticks = match.ticks_df.copy()
    if ticks.empty:
        return ticks

    cols = [
        "tick",
        "steamid",
        "name",
        "yaw",
        "pitch",
        "X",
        "Y",
        "Z",
        "health",
        "is_alive",
        "team_num",
        "team_name",
        "active_weapon_name",
        "is_scoped",
        "flash_duration",
        "spotted",
        "move_collide",
        "move_type",
        "looking_at_weapon",
        "holding_look_at_weapon",
        "buttons",
        "is_walking",
        "is_airborne",
        "usercmd_mouse_dx",
        "usercmd_mouse_dy",
        "usercmd_viewangle_x",
        "usercmd_viewangle_y",
        "velocity_X",
        "velocity_Y",
        "velocity_Z",
    ]
    cols = [c for c in cols if c in ticks.columns]
    ticks = ticks[cols].copy()
    starts = [int(x) for x in match.rounds["start_tick"].dropna().tolist()] if not match.rounds.empty else []
    ticks["round_num"] = ticks["tick"].apply(lambda t: cs2cd_adapter._assign_round_num(int(t), starts))
    ticks["steamid"] = ticks["steamid"].astype(str).str.strip()
    ticks["team_name"] = ticks.get("team_name", pd.Series("", index=ticks.index)).astype(str).str.upper()
    ticks = ticks[ticks["steamid"] != ""].copy()
    ticks = ticks.sort_values(["round_num", "tick", "steamid"]).reset_index(drop=True)
    return ticks


def player_name_map(ticks: pd.DataFrame) -> dict[str, str]:
    if ticks.empty or "steamid" not in ticks.columns:
        return {}
    names = ticks[["steamid", *([c for c in ["name"] if c in ticks.columns])]].copy()
    if "name" not in names.columns:
        return {}
    names["steamid"] = names["steamid"].astype(str).str.strip()
    names["name"] = names["name"].fillna("").astype(str).str.strip()
    names = names[(names["steamid"] != "") & (names["name"] != "")].copy()
    if names.empty:
        return {}
    return names.groupby("steamid")["name"].agg(lambda s: s.iloc[-1]).to_dict()


def build_tick_index(ticks: pd.DataFrame) -> dict[tuple[int, str], pd.DataFrame]:
    if ticks.empty:
        return {}
    out: dict[tuple[int, str], pd.DataFrame] = {}
    for (round_num, steamid), chunk in ticks.groupby(["round_num", "steamid"], sort=False):
        out[(int(round_num), str(steamid).strip())] = chunk.reset_index(drop=True)
    return out


def build_shot_index(shots: pd.DataFrame) -> dict[tuple[str, int], pd.DataFrame]:
    if shots.empty or not {"attacker_steamid", "round_num", "shot_tick"}.issubset(shots.columns):
        return {}
    out: dict[tuple[str, int], pd.DataFrame] = {}
    for (attacker, round_num), chunk in shots.groupby(["attacker_steamid", "round_num"], sort=False):
        out[(str(attacker).strip(), int(round_num))] = chunk.sort_values("shot_tick").reset_index(drop=True)
    return out


def build_pair_index(df: pd.DataFrame, tick_col: str) -> dict[tuple[str, str, int], pd.DataFrame]:
    required = {"attacker_steamid", "victim_steamid", "round_num", tick_col}
    if df.empty or not required.issubset(df.columns):
        return {}
    out: dict[tuple[str, str, int], pd.DataFrame] = {}
    for (attacker, victim, round_num), chunk in df.groupby(["attacker_steamid", "victim_steamid", "round_num"], sort=False):
        out[(str(attacker).strip(), str(victim).strip(), int(round_num))] = chunk.sort_values(tick_col).reset_index(drop=True)
    return out


def build_pair_tick_table(
    tick_index: dict[tuple[int, str], pd.DataFrame],
    attacker: str,
    victim: str,
    round_num: int,
    start_tick: int,
    end_tick: int,
) -> pd.DataFrame:
    a = tick_index.get((round_num, attacker))
    v = tick_index.get((round_num, victim))
    if a is None or v is None or a.empty or v.empty:
        return pd.DataFrame()
    a = a[(a["tick"] >= start_tick) & (a["tick"] <= end_tick)].copy()
    v = v[(v["tick"] >= start_tick) & (v["tick"] <= end_tick)].copy()
    if a.empty or v.empty:
        return pd.DataFrame()

    a = a.rename(
        columns={
            "X": "aX",
            "Y": "aY",
            "Z": "aZ",
            "yaw": "a_yaw",
            "pitch": "a_pitch",
            "health": "a_health",
            "is_alive": "a_alive",
            "active_weapon_name": "a_weapon",
            "is_scoped": "a_scoped",
            "flash_duration": "a_flash",
            "spotted": "a_spotted",
            "move_collide": "a_move_collide",
            "move_type": "a_move_type",
            "looking_at_weapon": "a_looking_weapon",
            "holding_look_at_weapon": "a_holding_look_weapon",
            "buttons": "a_buttons",
            "is_walking": "a_walking",
            "is_airborne": "a_airborne",
            "usercmd_mouse_dx": "a_mdx",
            "usercmd_mouse_dy": "a_mdy",
            "usercmd_viewangle_x": "a_cmd_pitch",
            "usercmd_viewangle_y": "a_cmd_yaw",
            "velocity_X": "a_vx",
            "velocity_Y": "a_vy",
            "velocity_Z": "a_vz",
            "team_name": "a_team_name",
        }
    )
    v = v.rename(
        columns={
            "X": "vX",
            "Y": "vY",
            "Z": "vZ",
            "yaw": "v_yaw",
            "pitch": "v_pitch",
            "health": "v_health",
            "is_alive": "v_alive",
            "active_weapon_name": "v_weapon",
            "is_scoped": "v_scoped",
            "flash_duration": "v_flash",
            "spotted": "v_spotted",
            "move_collide": "v_move_collide",
            "move_type": "v_move_type",
            "looking_at_weapon": "v_looking_weapon",
            "holding_look_at_weapon": "v_holding_look_weapon",
            "buttons": "v_buttons",
            "is_walking": "v_walking",
            "is_airborne": "v_airborne",
            "velocity_X": "v_vx",
            "velocity_Y": "v_vy",
            "velocity_Z": "v_vz",
            "team_name": "v_team_name",
        }
    )
    keep_a = [c for c in ["tick", "aX", "aY", "aZ", "a_yaw", "a_pitch", "a_health", "a_alive", "a_weapon", "a_scoped", "a_flash", "a_spotted", "a_move_collide", "a_move_type", "a_looking_weapon", "a_holding_look_weapon", "a_buttons", "a_walking", "a_airborne", "a_mdx", "a_mdy", "a_cmd_pitch", "a_cmd_yaw", "a_vx", "a_vy", "a_vz", "a_team_name"] if c in a.columns]
    keep_v = [c for c in ["tick", "vX", "vY", "vZ", "v_health", "v_alive", "v_weapon", "v_scoped", "v_flash", "v_spotted", "v_move_collide", "v_move_type", "v_looking_weapon", "v_holding_look_weapon", "v_buttons", "v_walking", "v_airborne", "v_vx", "v_vy", "v_vz", "v_team_name"] if c in v.columns]
    joined = a[keep_a].merge(v[keep_v], on="tick", how="inner").sort_values("tick").reset_index(drop=True)
    return joined


def enrich_pair_ticks(tv: pd.DataFrame) -> pd.DataFrame:
    if tv.empty:
        return tv
    out = tv.copy()
    dx = out["vX"] - out["aX"]
    dy = out["vY"] - out["aY"]
    dz = (out["vZ"] + CHEST_Z) - (out["aZ"] + EYE_Z)
    out["distance"] = np.sqrt(dx * dx + dy * dy + dz * dz)
    out["target_yaw"] = np.degrees(np.arctan2(dy, dx))
    out["target_pitch"] = -np.degrees(np.arctan2(dz, np.hypot(dx, dy)))
    out["aim_error_deg"] = np.sqrt(
        np.square((out["target_yaw"] - out["a_yaw"]).map(wrap_deg))
        + np.square((out["target_pitch"] - out["a_pitch"]).map(wrap_deg))
    )
    if "a_mdx" in out.columns and "a_mdy" in out.columns:
        out["mouse_delta_abs"] = np.sqrt(
            np.square(pd.to_numeric(out["a_mdx"], errors="coerce").fillna(0.0))
            + np.square(pd.to_numeric(out["a_mdy"], errors="coerce").fillna(0.0))
        )
    else:
        out["mouse_delta_abs"] = np.nan
    out["in_front_cone"] = out["aim_error_deg"] <= MAX_FOV_ERR_DEG
    out["both_alive"] = _bool_series(out["a_alive"], out.index) & _bool_series(out["v_alive"], out.index)
    out["candidate"] = out["both_alive"] & out["in_front_cone"]
    return out


def first_candidate_tick(tv: pd.DataFrame, anchor_tick: int) -> float:
    g = tv[(tv["tick"] <= anchor_tick) & (tv["tick"] >= anchor_tick - W_PRE) & (tv["candidate"])]
    if g.empty:
        return np.nan
    return float(g["tick"].min())


def first_shot_tick(shots: pd.DataFrame, attacker: str, round_num: int, start_tick: int, end_tick: int) -> float:
    required = {"attacker_steamid", "shot_tick", "round_num"}
    if shots.empty or not required.issubset(set(shots.columns)):
        return np.nan
    g = shots[(shots["attacker_steamid"] == attacker) & (shots["round_num"] == round_num)]
    if g.empty:
        return np.nan
    g = g[(g["shot_tick"] >= start_tick) & (g["shot_tick"] <= end_tick)]
    if g.empty:
        return np.nan
    return float(g["shot_tick"].min())


def first_shot_tick_indexed(shot_index: dict[tuple[str, int], pd.DataFrame], attacker: str, round_num: int, start_tick: int, end_tick: int) -> float:
    g = shot_index.get((attacker, round_num))
    if g is None or g.empty:
        return np.nan
    g = g[(g["shot_tick"] >= start_tick) & (g["shot_tick"] <= end_tick)]
    if g.empty:
        return np.nan
    return float(g["shot_tick"].iloc[0])


def _shots_last_window(shots: pd.DataFrame, attacker: str, kill_tick: int, width: int) -> int:
    required = {"attacker_steamid", "shot_tick"}
    if shots.empty or not required.issubset(set(shots.columns)):
        return 0
    g = shots[(shots["attacker_steamid"] == attacker) & (shots["shot_tick"] <= kill_tick) & (shots["shot_tick"] >= kill_tick - width)]
    return int(len(g))


def shots_last_window_indexed(shot_index: dict[tuple[str, int], pd.DataFrame], attacker: str, round_num: int, kill_tick: int, width: int) -> int:
    g = shot_index.get((attacker, round_num))
    if g is None or g.empty:
        return 0
    g = g[(g["shot_tick"] <= kill_tick) & (g["shot_tick"] >= kill_tick - width)]
    return int(len(g))


def _angular_stats(values: list[float]) -> dict[str, float]:
    return {
        "mean": _mean(values) if values else np.nan,
        "p90": _quantile(values, 0.90) if values else np.nan,
        "max": max(values) if values else np.nan,
        "std": _std(values) if values else np.nan,
    }


def compute_pair_motion(enc: pd.DataFrame) -> dict[str, float]:
    if enc.empty or len(enc) < 2:
        return {
            "angular_velocity_mean": np.nan,
            "angular_velocity_p90": np.nan,
            "angular_velocity_max": np.nan,
            "angular_velocity_std": np.nan,
            "angular_jerk_mean": np.nan,
            "angular_jerk_p90": np.nan,
            "angular_jerk_max": np.nan,
            "distance_mean": float(enc["distance"].mean()) if "distance" in enc and not enc.empty else np.nan,
            "distance_min": float(enc["distance"].min()) if "distance" in enc and not enc.empty else np.nan,
            "distance_p90": float(enc["distance"].quantile(0.9)) if "distance" in enc and not enc.empty else np.nan,
            "distance_max": float(enc["distance"].max()) if "distance" in enc and not enc.empty else np.nan,
            "distance_std": np.nan,
            "closing_speed_mean": np.nan,
            "closing_speed_p90": np.nan,
            "closing_speed_max": np.nan,
            "attacker_speed_mean": np.nan,
            "attacker_speed_p90": np.nan,
            "victim_speed_mean": np.nan,
            "victim_speed_p90": np.nan,
            "relative_speed_mean": np.nan,
            "relative_speed_p90": np.nan,
            "los_angular_velocity_mean": np.nan,
            "los_angular_velocity_p90": np.nan,
            "los_angular_velocity_max": np.nan,
            "los_angular_jerk_mean": np.nan,
            "los_angular_jerk_p90": np.nan,
            "los_angular_jerk_max": np.nan,
        }

    velocities = []
    jerks = []
    los_velocities = []
    los_jerks = []
    closing = []
    attacker_speed = []
    victim_speed = []
    relative_speed = []
    prev_v = None
    prev_los_v = None
    prev = enc.iloc[0]
    for _, row in enc.iloc[1:].iterrows():
        dt = max(1, int(row["tick"]) - int(prev["tick"]))
        av = math.hypot(wrap_deg(float(row["a_yaw"]) - float(prev["a_yaw"])), wrap_deg(float(row["a_pitch"]) - float(prev["a_pitch"]))) / dt
        velocities.append(av)
        if prev_v is not None:
            jerks.append(abs(av - prev_v) / dt)
        prev_v = av

        lv = math.hypot(wrap_deg(float(row["target_yaw"]) - float(prev["target_yaw"])), wrap_deg(float(row["target_pitch"]) - float(prev["target_pitch"]))) / dt
        los_velocities.append(lv)
        if prev_los_v is not None:
            los_jerks.append(abs(lv - prev_los_v) / dt)
        prev_los_v = lv

        closing.append((float(prev["distance"]) - float(row["distance"])) / dt)
        attacker_speed.append(math.sqrt(sum(float(row[c] or 0.0) ** 2 for c in ["a_vx", "a_vy", "a_vz"] if c in row.index)))
        victim_speed.append(math.sqrt(sum(float(row[c] or 0.0) ** 2 for c in ["v_vx", "v_vy", "v_vz"] if c in row.index)))
        rvx = float(row.get("v_vx", 0.0) or 0.0) - float(row.get("a_vx", 0.0) or 0.0)
        rvy = float(row.get("v_vy", 0.0) or 0.0) - float(row.get("a_vy", 0.0) or 0.0)
        rvz = float(row.get("v_vz", 0.0) or 0.0) - float(row.get("a_vz", 0.0) or 0.0)
        relative_speed.append(math.sqrt(rvx * rvx + rvy * rvy + rvz * rvz))
        prev = row

    ang = _angular_stats(velocities)
    los = _angular_stats(los_velocities)
    return {
        "angular_velocity_mean": ang["mean"],
        "angular_velocity_p90": ang["p90"],
        "angular_velocity_max": ang["max"],
        "angular_velocity_std": ang["std"],
        "angular_jerk_mean": _mean(jerks) if jerks else np.nan,
        "angular_jerk_p90": _quantile(jerks, 0.90) if jerks else np.nan,
        "angular_jerk_max": max(jerks) if jerks else np.nan,
        "distance_mean": float(enc["distance"].mean()),
        "distance_min": float(enc["distance"].min()),
        "distance_p90": float(enc["distance"].quantile(0.9)),
        "distance_max": float(enc["distance"].max()),
        "distance_std": float(enc["distance"].std(ddof=1)) if len(enc) > 1 else np.nan,
        "closing_speed_mean": _mean(closing) if closing else np.nan,
        "closing_speed_p90": _quantile(closing, 0.90) if closing else np.nan,
        "closing_speed_max": max(closing) if closing else np.nan,
        "attacker_speed_mean": _mean(attacker_speed) if attacker_speed else np.nan,
        "attacker_speed_p90": _quantile(attacker_speed, 0.90) if attacker_speed else np.nan,
        "victim_speed_mean": _mean(victim_speed) if victim_speed else np.nan,
        "victim_speed_p90": _quantile(victim_speed, 0.90) if victim_speed else np.nan,
        "relative_speed_mean": _mean(relative_speed) if relative_speed else np.nan,
        "relative_speed_p90": _quantile(relative_speed, 0.90) if relative_speed else np.nan,
        "los_angular_velocity_mean": los["mean"],
        "los_angular_velocity_p90": los["p90"],
        "los_angular_velocity_max": los["max"],
        "los_angular_jerk_mean": _mean(los_jerks) if los_jerks else np.nan,
        "los_angular_jerk_p90": _quantile(los_jerks, 0.90) if los_jerks else np.nan,
        "los_angular_jerk_max": max(los_jerks) if los_jerks else np.nan,
    }


def build_kill_rows(
    match: cs2cd_adapter.CS2CDMatch,
    tick_index: dict[tuple[int, str], pd.DataFrame],
    shot_index: dict[tuple[str, int], pd.DataFrame],
    names: dict[str, str] | None = None,
) -> pd.DataFrame:
    kills = match.kills.copy()
    if kills.empty:
        return pd.DataFrame()

    rows = []
    names = names or {}
    for k in kills.itertuples(index=False):
        attacker = str(k.attacker_steamid).strip()
        victim = str(k.victim_steamid).strip()
        kill_tick = int(k.kill_tick)
        round_num = int(k.round_num)
        tv = build_pair_tick_table(tick_index, attacker, victim, round_num, max(0, kill_tick - W_PRE), kill_tick)
        if not tv.empty:
            tv = enrich_pair_ticks(tv)
            t0 = first_candidate_tick(tv, kill_tick)
        else:
            t0 = np.nan
        first_shot = first_shot_tick_indexed(shot_index, attacker, round_num, max(0, kill_tick - W_PRE), kill_tick)
        rt = float(first_shot - t0) if pd.notna(first_shot) and pd.notna(t0) else np.nan
        vis_before_shot = float(first_shot - t0) if pd.notna(first_shot) and pd.notna(t0) else np.nan
        vis_before_kill = float(kill_tick - t0) if pd.notna(t0) else np.nan
        label = 1 if attacker in match.cheater_ids else 0
        rows.append(
            {
                "demo_id": match.demo_id,
                "map_name": match.map_name,
                "round_num": round_num,
                "kill_tick": kill_tick,
                "t0_visible": t0,
                "first_shot_tick": first_shot,
                "rt_ticks": rt,
                "attacker_steamid": attacker,
                "attacker_name": names.get(attacker, attacker),
                "victim_steamid": victim,
                "victim_name": names.get(victim, victim),
                "weapon": str(getattr(k, "weapon", "")),
                "headshot": bool(getattr(k, "headshot", False)),
                "distance": float(getattr(k, "distance", np.nan)),
                "visible_ticks_before_shot": vis_before_shot,
                "visible_ticks_before_kill": vis_before_kill,
                "shots_last64_before_kill": shots_last_window_indexed(shot_index, attacker, round_num, kill_tick, 64),
                "shots_last128_before_kill": shots_last_window_indexed(shot_index, attacker, round_num, kill_tick, 128),
                "is_micropeek_4": bool(pd.notna(vis_before_shot) and vis_before_shot <= 4),
                "is_micropeek_6": bool(pd.notna(vis_before_shot) and vis_before_shot <= 6),
                "is_micropeek_8": bool(pd.notna(vis_before_shot) and vis_before_shot <= 8),
                "is_prefire": bool(pd.notna(rt) and rt <= -2),
                "is_thrusmoke": bool(getattr(k, "is_thrusmoke", False)),
                "label": int(label),
                "label_source": "cs2cd_cheaters_json",
                "dataset_source": "cs2cd",
            }
        )
    return pd.DataFrame(rows)


def build_encounter_rows(
    match: cs2cd_adapter.CS2CDMatch,
    tick_index: dict[tuple[int, str], pd.DataFrame],
    shot_index: dict[tuple[str, int], pd.DataFrame],
    damage_index: dict[tuple[str, str, int], pd.DataFrame],
    kill_index: dict[tuple[str, str, int], pd.DataFrame],
    names: dict[str, str] | None = None,
) -> pd.DataFrame:
    damages = match.damages.copy()
    kills = match.kills.copy()
    if damages.empty and kills.empty:
        return empty_encounters_df()

    anchor_rows = []
    if not damages.empty:
        for row in damages.itertuples(index=False):
            anchor_rows.append(
                {
                    "kind": "damage",
                    "tick": int(row.tick),
                    "round_num": int(row.round_num),
                    "attacker_steamid": str(row.attacker_steamid).strip(),
                    "victim_steamid": str(row.victim_steamid).strip(),
                }
            )
    if not kills.empty:
        for row in kills.itertuples(index=False):
            anchor_rows.append(
                {
                    "kind": "kill",
                    "tick": int(row.kill_tick),
                    "round_num": int(row.round_num),
                    "attacker_steamid": str(row.attacker_steamid).strip(),
                    "victim_steamid": str(row.victim_steamid).strip(),
                }
            )
    anchor_df = pd.DataFrame(anchor_rows).drop_duplicates(subset=["round_num", "attacker_steamid", "victim_steamid", "tick"]).sort_values(["round_num", "tick"])
    out = []
    names = names or {}

    for anchor in anchor_df.itertuples(index=False):
        round_num = int(anchor.round_num)
        attacker = str(anchor.attacker_steamid)
        victim = str(anchor.victim_steamid)
        tick = int(anchor.tick)
        tv = build_pair_tick_table(tick_index, attacker, victim, round_num, max(0, tick - W_PRE), tick + KILL_WITHIN_TICKS)
        if tv.empty:
            continue
        tv = enrich_pair_ticks(tv)
        cand = tv[tv["candidate"]].copy()
        if cand.empty:
            continue
        start_tick = int(cand["tick"].min())
        end_tick = min(int(cand["tick"].max()), start_tick + ENCOUNTER_TIMEOUT_TICKS)
        enc = tv[(tv["tick"] >= start_tick) & (tv["tick"] <= end_tick) & (tv["candidate"])].copy()
        if enc.empty:
            continue

        shot_rows = shot_index.get((attacker, round_num), pd.DataFrame(columns=["shot_tick", "weapon"]))
        if not shot_rows.empty:
            shot_rows = shot_rows[(shot_rows["shot_tick"] >= start_tick) & (shot_rows["shot_tick"] <= end_tick)].copy()
        damage_rows = damage_index.get(
            (attacker, victim, round_num),
            pd.DataFrame(columns=["tick", "damage_dir_x", "damage_dir_y", "damage_dir_z", "num_penetrations", "no_scope", "in_air"]),
        )
        if not damage_rows.empty:
            damage_rows = damage_rows[(damage_rows["tick"] >= start_tick) & (damage_rows["tick"] <= end_tick)].copy()
        kill_rows = kill_index.get((attacker, victim, round_num), pd.DataFrame(columns=["kill_tick", "weapon"]))
        if not kill_rows.empty:
            kill_rows = kill_rows[(kill_rows["kill_tick"] >= start_tick) & (kill_rows["kill_tick"] <= end_tick + KILL_WITHIN_TICKS)].copy()

        first_shot = float(shot_rows["shot_tick"].min()) if not shot_rows.empty else np.nan
        first_damage = float(damage_rows["tick"].min()) if not damage_rows.empty else np.nan
        aim_lock = enc[enc["aim_error_deg"] <= AIM_ACQUIRE_ERR_DEG]
        aim_lock_tick = float(aim_lock["tick"].min()) if not aim_lock.empty else np.nan
        shot_ticks = shot_rows["shot_tick"].astype(float).tolist()
        shot_gaps = [shot_ticks[i] - shot_ticks[i - 1] for i in range(1, len(shot_ticks))]
        aim_errors = enc["aim_error_deg"].astype(float).tolist()
        enc_ticks = enc["tick"].astype(float).tolist()

        angular_velocity_inst: list[float] = []
        angular_jerk_inst: list[float] = []
        prev_v = None
        prev_row = enc.iloc[0]
        for _, row in enc.iloc[1:].iterrows():
            dt = max(1, int(row["tick"]) - int(prev_row["tick"]))
            av = math.hypot(wrap_deg(float(row["a_yaw"]) - float(prev_row["a_yaw"])), wrap_deg(float(row["a_pitch"]) - float(prev_row["a_pitch"]))) / dt
            angular_velocity_inst.append(float(av))
            if prev_v is not None:
                angular_jerk_inst.append(float(abs(av - prev_v) / dt))
            prev_v = av
            prev_row = row

        first_err = float(aim_errors[0]) if aim_errors else np.nan
        min_err = float(min(aim_errors)) if aim_errors else np.nan
        min_idx = int(np.argmin(aim_errors)) if aim_errors else 0
        min_tick = float(enc_ticks[min_idx]) if aim_errors else np.nan
        aim_error_range = float(first_err - min_err) if aim_errors else np.nan
        aim_error_collapse_rate = (
            float(aim_error_range / max(1.0, float(min_tick - start_tick)))
            if pd.notna(min_tick) and pd.notna(aim_error_range)
            else np.nan
        )
        aim_error_collapse_ratio = (
            float(first_err / max(0.25, min_err))
            if pd.notna(first_err) and pd.notna(min_err)
            else np.nan
        )
        aim_error_min_tick_offset = float(min_tick - start_tick) if pd.notna(min_tick) else np.nan
        aim_correction_flips = int(_count_direction_flips(aim_errors))
        post_acquire_errors = aim_lock["aim_error_deg"].astype(float).tolist() if not aim_lock.empty else []
        pre_shot_errors = (
            enc[(enc["tick"] <= first_shot) & (enc["tick"] >= first_shot - 8)]["aim_error_deg"].astype(float).tolist()
            if pd.notna(first_shot)
            else []
        )
        early_vel = angular_velocity_inst[: min(len(angular_velocity_inst), 12)]
        to_shot_vel = angular_velocity_inst[: max(0, len(enc[enc["tick"] <= first_shot]) - 1)] if pd.notna(first_shot) else angular_velocity_inst
        early_jerk = angular_jerk_inst[: min(len(angular_jerk_inst), 12)]
        to_shot_jerk = angular_jerk_inst[: max(0, len(enc[enc["tick"] <= first_shot]) - 2)] if pd.notna(first_shot) else angular_jerk_inst
        mouse_abs = pd.to_numeric(enc.get("mouse_delta_abs"), errors="coerce").dropna().astype(float).tolist()
        mouse_dx = pd.to_numeric(enc.get("a_mdx"), errors="coerce").dropna().astype(float).tolist() if "a_mdx" in enc.columns else []
        mouse_dy = pd.to_numeric(enc.get("a_mdy"), errors="coerce").dropna().astype(float).tolist() if "a_mdy" in enc.columns else []
        pre_shot_mouse = (
            pd.to_numeric(enc[(enc["tick"] <= first_shot) & (enc["tick"] >= first_shot - 8)]["mouse_delta_abs"], errors="coerce").dropna().astype(float).tolist()
            if pd.notna(first_shot) and "mouse_delta_abs" in enc.columns
            else []
        )
        post_acquire_mouse = (
            pd.to_numeric(aim_lock.get("mouse_delta_abs"), errors="coerce").dropna().astype(float).tolist()
            if not aim_lock.empty and "mouse_delta_abs" in aim_lock.columns
            else []
        )
        walking_ticks = _bool_series(enc.get("a_walking", pd.Series(False, index=enc.index)), enc.index)
        airborne_ticks = _bool_series(enc.get("a_airborne", pd.Series(False, index=enc.index)), enc.index)

        damage_dir_delta = []
        if len(damage_rows) >= 2:
            dr = damage_rows.sort_values("tick")
            prev = None
            for _, row in dr.iterrows():
                vec = np.array([float(row["damage_dir_x"]), float(row["damage_dir_y"]), float(row["damage_dir_z"])], dtype=float)
                norm = np.linalg.norm(vec)
                if norm > 0:
                    vec = vec / norm
                if prev is not None:
                    dot = float(np.clip(np.dot(prev, vec), -1.0, 1.0))
                    damage_dir_delta.append(float(math.degrees(math.acos(dot))))
                prev = vec

        motion = compute_pair_motion(enc)
        out.append(
            {
                "demo_id": match.demo_id,
                "map_name": match.map_name,
                "round_num": round_num,
                "encounter_id": f"{match.demo_id}_{attacker}_{victim}_{start_tick}_{end_tick}",
                "attacker_steamid": attacker,
                "attacker_name": names.get(attacker, attacker),
                "victim_steamid": victim,
                "victim_name": names.get(victim, victim),
                "attacker_side": str(enc.get("a_team_name", pd.Series([""])).iloc[0]).lower(),
                "victim_side": str(enc.get("v_team_name", pd.Series([""])).iloc[0]).lower(),
                "start_tick": start_tick,
                "end_tick": end_tick,
                "exposure_duration": int(end_tick - start_tick + 1),
                "visible_tick_count": int(len(enc)),
                "occluded_tick_count": 0,
                "visible_ratio": 1.0,
                "time_to_first_shot": float(first_shot - start_tick) if pd.notna(first_shot) else np.nan,
                "time_to_first_damage": float(first_damage - start_tick) if pd.notna(first_damage) else np.nan,
                "aim_error_at_first_visible": float(enc["aim_error_deg"].iloc[0]),
                "aim_error_min": float(enc["aim_error_deg"].min()),
                "aim_error_p10": float(enc["aim_error_deg"].quantile(0.1)),
                "aim_error_p90": float(enc["aim_error_deg"].quantile(0.9)),
                "aim_acquire_time": float(aim_lock_tick - start_tick) if pd.notna(aim_lock_tick) else np.nan,
                "aim_dwell_ticks": int((enc["aim_error_deg"] <= AIM_ACQUIRE_ERR_DEG).sum()),
                "aim_error_range": aim_error_range,
                "aim_error_collapse_rate": aim_error_collapse_rate,
                "aim_error_collapse_ratio": aim_error_collapse_ratio,
                "aim_error_min_tick_offset": aim_error_min_tick_offset,
                "aim_correction_flips": aim_correction_flips,
                "post_acquire_error_mean": _mean(post_acquire_errors) if post_acquire_errors else np.nan,
                "post_acquire_error_std": _std(post_acquire_errors) if post_acquire_errors else np.nan,
                "pre_shot_aim_error_mean": _mean(pre_shot_errors) if pre_shot_errors else np.nan,
                "pre_shot_aim_error_std": _std(pre_shot_errors) if pre_shot_errors else np.nan,
                "acquire_to_shot_lag": float(first_shot - aim_lock_tick) if pd.notna(first_shot) and pd.notna(aim_lock_tick) else np.nan,
                "snap_velocity_early_max": max(early_vel) if early_vel else np.nan,
                "snap_velocity_to_shot_max": max(to_shot_vel) if to_shot_vel else np.nan,
                "snap_jerk_early_max": max(early_jerk) if early_jerk else np.nan,
                "snap_jerk_to_shot_max": max(to_shot_jerk) if to_shot_jerk else np.nan,
                "mouse_delta_abs_mean": _mean(mouse_abs) if mouse_abs else np.nan,
                "mouse_delta_abs_p90": _quantile(mouse_abs, 0.90) if mouse_abs else np.nan,
                "mouse_delta_abs_max": max(mouse_abs) if mouse_abs else np.nan,
                "mouse_delta_abs_std": _std(mouse_abs) if mouse_abs else np.nan,
                "mouse_dx_flip_rate": float(_count_direction_flips(mouse_dx) / max(1, len(mouse_dx) - 1)) if len(mouse_dx) >= 2 else np.nan,
                "mouse_dy_flip_rate": float(_count_direction_flips(mouse_dy) / max(1, len(mouse_dy) - 1)) if len(mouse_dy) >= 2 else np.nan,
                "pre_shot_mouse_burst_max": max(pre_shot_mouse) if pre_shot_mouse else np.nan,
                "post_acquire_mouse_quiet_rate": float(sum(v <= 2.0 for v in post_acquire_mouse) / len(post_acquire_mouse)) if post_acquire_mouse else np.nan,
                "walking_tick_rate": float(walking_ticks.mean()) if len(walking_ticks) else np.nan,
                "airborne_tick_rate": float(airborne_ticks.mean()) if len(airborne_ticks) else np.nan,
                "shot_before_aim_acquire": bool(pd.notna(first_shot) and pd.notna(aim_lock_tick) and first_shot < aim_lock_tick),
                "shot_count": int(len(shot_rows)),
                "shot_rate_per_128": float(len(shot_rows) * 128.0 / max(1, end_tick - start_tick + 1)),
                "mean_shot_gap": _mean(shot_gaps) if shot_gaps else np.nan,
                "damage_count": int(len(damage_rows)),
                "damage_total": float(len(damage_rows)),
                "ended_in_damage": bool(not damage_rows.empty),
                "ended_in_kill_within_y": bool(not kill_rows.empty),
                "kill_tick": float(kill_rows["kill_tick"].min()) if not kill_rows.empty else np.nan,
                "weapon": str(kill_rows["weapon"].iloc[0]) if not kill_rows.empty else (str(shot_rows["weapon"].iloc[0]) if not shot_rows.empty else ""),
                **motion,
                "damage_dir_delta_mean": _mean(damage_dir_delta) if damage_dir_delta else np.nan,
                "damage_dir_delta_p90": _quantile(damage_dir_delta, 0.90) if damage_dir_delta else np.nan,
                "penetration_count": int(damage_rows["num_penetrations"].fillna(0).astype(int).sum()) if not damage_rows.empty else 0,
                "no_scope_damage_count": int(_bool_series(damage_rows["no_scope"], damage_rows.index).sum()) if not damage_rows.empty else 0,
                "in_air_damage_count": int(_bool_series(damage_rows["in_air"], damage_rows.index).sum()) if not damage_rows.empty else 0,
                "label": int(attacker in match.cheater_ids),
                "label_source": "cs2cd_cheaters_json",
                "dataset_source": "cs2cd",
            }
        )

    if not out:
        return empty_encounters_df()
    df = pd.DataFrame(out).drop_duplicates(subset=["encounter_id"]).sort_values(["round_num", "start_tick", "attacker_steamid"])
    return df


def build_match_outputs(match: cs2cd_adapter.CS2CDMatch) -> tuple[pd.DataFrame, pd.DataFrame]:
    ticks = prepare_ticks(match)
    names = player_name_map(ticks)
    tick_index = build_tick_index(ticks)
    shots = match.shots.copy()
    starts = [int(x) for x in match.rounds["start_tick"].dropna().tolist()] if not match.rounds.empty else []
    if not shots.empty:
        if "shot_tick" in shots.columns:
            shots["round_num"] = shots["shot_tick"].apply(lambda t: cs2cd_adapter._assign_round_num(int(t), starts))
        else:
            shots["round_num"] = pd.Series(dtype="int64")
    else:
        shots["round_num"] = pd.Series(dtype="int64")
    shot_index = build_shot_index(shots)
    damage_index = build_pair_index(match.damages.copy(), "tick")
    kill_index = build_pair_index(match.kills.copy(), "kill_tick")
    kill_rows = build_kill_rows(match, tick_index, shot_index, names=names)
    encounter_rows = build_encounter_rows(match, tick_index, shot_index, damage_index, kill_index, names=names)
    return kill_rows, encounter_rows


def _demo_paths(split: str, match_id: str) -> tuple[str, Path, Path, Path, Path]:
    demo_id = f"CS2CD_{split}_{match_id}"
    demo_dir = OUT_ROOT / demo_id
    out_path = demo_dir / "engagement_features.parquet"
    encounter_out_path = demo_dir / "encounters.parquet"
    meta_path = demo_dir / "meta.json"
    return demo_id, demo_dir, out_path, encounter_out_path, meta_path


def process_one_match(split: str, match_id: str, overwrite: bool) -> tuple[str, str, str | None]:
    demo_id, demo_dir, out_path, encounter_out_path, meta_path = _demo_paths(split, match_id)
    try:
        if out_path.exists() and encounter_out_path.exists() and not overwrite:
            return "skipped", demo_id, None

        match = cs2cd_adapter.load_match(split, match_id)
        demo_dir.mkdir(parents=True, exist_ok=True)
        kill_rows, encounter_rows = build_match_outputs(match)
        if kill_rows.empty:
            return "skipped", demo_id, "empty kill rows"

        kill_rows.to_parquet(out_path, index=False)
        encounter_rows.to_parquet(encounter_out_path, index=False)
        meta_path.write_text(
            (
                "{\n"
                f'  "demo_id": "{match.demo_id}",\n'
                f'  "split": "{split}",\n'
                f'  "match_id": "{match_id}",\n'
                f'  "map_name": "{match.map_name}",\n'
                f'  "n_kills": {int(len(kill_rows))},\n'
                f'  "n_encounters": {int(len(encounter_rows))},\n'
                f'  "n_cheaters_annotated": {int(len(match.cheater_ids))}\n'
                "}\n"
            ),
            encoding="utf-8",
        )
        return "built", demo_id, None
    except Exception as exc:
        err = "".join(traceback.format_exception_only(type(exc), exc)).strip()
        return "failed", demo_id, err


def process_split(split: str, max_matches: int | None, overwrite: bool, workers: int) -> tuple[int, int, int]:
    ids = cs2cd_adapter.list_match_ids(split)
    if max_matches is not None:
        ids = ids[:max_matches]

    built = 0
    skipped = 0
    failed = 0

    todo: list[str] = []
    for mid in ids:
        _, _, out_path, encounter_out_path, _ = _demo_paths(split, mid)
        if out_path.exists() and encounter_out_path.exists() and not overwrite:
            skipped += 1
        else:
            todo.append(mid)

    total = len(ids)
    print(f"[INFO] split={split} total={total} pre_skipped={skipped} todo={len(todo)} workers={workers}")

    if not todo:
        return built, skipped, failed

    if int(workers) <= 1:
        for idx, mid in enumerate(todo, start=1):
            status, demo_id, err = process_one_match(split, mid, overwrite)
            if status == "built":
                built += 1
                print(f"[BUILD {idx}/{len(todo)}] {demo_id}")
            elif status == "skipped":
                skipped += 1
                print(f"[SKIP {idx}/{len(todo)}] {demo_id} {f'({err})' if err else ''}".rstrip())
            else:
                failed += 1
                print(f"[FAIL {idx}/{len(todo)}] {demo_id}: {err}")
        return built, skipped, failed

    max_workers = max(1, min(int(workers), os.cpu_count() or 1))
    with ProcessPoolExecutor(max_workers=max_workers) as ex:
        futs = {ex.submit(process_one_match, split, mid, overwrite): mid for mid in todo}
        done_n = 0
        for fut in as_completed(futs):
            done_n += 1
            status, demo_id, err = fut.result()
            if status == "built":
                built += 1
                print(f"[BUILD {done_n}/{len(todo)}] {demo_id}")
            elif status == "skipped":
                skipped += 1
                print(f"[SKIP {done_n}/{len(todo)}] {demo_id} {f'({err})' if err else ''}".rstrip())
            else:
                failed += 1
                print(f"[FAIL {done_n}/{len(todo)}] {demo_id}: {err}")

    return built, skipped, failed


def main() -> int:
    args = parse_args()
    total_built = 0
    total_skipped = 0
    total_failed = 0
    for split in cs2cd_adapter.SPLITS:
        built, skipped, failed = process_split(split, args.max_matches, args.overwrite, args.workers)
        total_built += built
        total_skipped += skipped
        total_failed += failed
        print(f"[INFO] split={split} built={built} skipped={skipped} failed={failed}")
    print(f"[OK] CS2CD engagement build complete. built={total_built} skipped={total_skipped} failed={total_failed}")
    return 0 if total_failed == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

from bisect import bisect_left, bisect_right
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
import argparse
import io
import math
import os
import sys
import zipfile

import polars as pl

MAIN_ROOT = Path(__file__).resolve().parents[2]
if str(MAIN_ROOT) not in sys.path:
    sys.path.insert(0, str(MAIN_ROOT))

from src.utils.project_paths import DEMOS_ROOT, PARSED_ZIPS_ROOT
from src.utils.visibility_awpy import Point3, is_visible, map_name_from_zip

# ---------------- CONFIG ----------------
ZIPS_DIR = PARSED_ZIPS_ROOT
OUT_ROOT = DEMOS_ROOT

W_PRE = 128
REQ_CONSEC = 2
EYE_Z = 64
CHEST_Z = 56
LONG_RANGE_DIST = 1500.0
MAX_LOS_DISTANCE = 3000.0

ENCOUNTER_BREAK_TICKS = 8
ENCOUNTER_TIMEOUT_TICKS = 192
KILL_WITHIN_TICKS = 16
AIM_ACQUIRE_ERR_DEG = 5.0

MAX_DEMOS = None
OVERWRITE = True
# ----------------------------------------


def default_workers() -> int:
    cpu = os.cpu_count() or 4
    return max(1, min(4, cpu - 2))


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Build kill-level engagement features and encounter features from parsed zip demos.")
    ap.add_argument("--workers", type=int, default=default_workers(), help="Parallel worker processes. Default leaves headroom for desktop use.")
    ap.add_argument("--max-demos", type=int, default=MAX_DEMOS, help="Optional cap for debugging or partial rebuilds.")
    ap.add_argument("--overwrite", action="store_true", help="Force rebuild even when outputs already have the current schema.")
    return ap.parse_args()


def outputs_current(kill_out_path: Path, encounter_out_path: Path) -> bool:
    if not kill_out_path.exists() or not encounter_out_path.exists():
        return False
    try:
        cols = set(pl.read_parquet(encounter_out_path, n_rows=0).columns)
    except Exception:
        return False
    return {"attacker_side", "victim_side"}.issubset(cols)


def wrap_deg(x: float) -> float:
    return ((float(x) + 180.0) % 360.0) - 180.0


def aim_error_deg(att_yaw: float, att_pitch: float, dx: float, dy: float, dz: float) -> float:
    tgt_yaw = math.degrees(math.atan2(dy, dx))
    horiz = math.hypot(dx, dy)
    tgt_pitch = -math.degrees(math.atan2(dz, horiz))
    dyaw = wrap_deg(tgt_yaw - att_yaw)
    dpitch = wrap_deg(tgt_pitch - att_pitch)
    return math.hypot(dyaw, dpitch)


def _to_float(value) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


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


def _first_in_range(values: list[int], start_tick: int, end_tick: int) -> int | None:
    if not values:
        return None
    lo = bisect_left(values, start_tick)
    if lo < len(values) and values[lo] <= end_tick:
        return int(values[lo])
    return None


def _slice_in_range(values: list[int], start_tick: int, end_tick: int) -> list[int]:
    if not values:
        return []
    lo = bisect_left(values, start_tick)
    hi = bisect_right(values, end_tick)
    return [int(v) for v in values[lo:hi]]


def _events_in_range(
    events: list[dict[str, object]],
    start_tick: int,
    end_tick: int,
) -> list[dict[str, object]]:
    if not events:
        return []
    ticks = [int(ev["tick"]) for ev in events]
    lo = bisect_left(ticks, start_tick)
    hi = bisect_right(ticks, end_tick)
    return events[lo:hi]


def first_visible_tick_los(
    ticks: pl.DataFrame,
    map_name: str,
    attacker_id: int,
    victim_id: int,
    kill_tick: int,
) -> int | None:
    start = max(0, kill_tick - W_PRE)
    tv = build_pair_tick_table(ticks, attacker_id, victim_id, start, kill_tick)
    if tv.is_empty():
        return None

    consec = 0
    first_tick = None
    for row in iter_pair_visibility(tv, map_name):
        t = int(row["tick"])
        if row["is_visible"]:
            consec += 1
            if first_tick is None:
                first_tick = t
            if consec >= REQ_CONSEC:
                return first_tick
        else:
            consec = 0
            first_tick = None

    return None


def first_shot_tick(
    shots: pl.DataFrame,
    attacker_id: int,
    start_tick: int,
    kill_tick: int,
) -> int | None:
    s = shots.filter(
        (pl.col("player_steamid") == attacker_id)
        & (pl.col("tick") >= start_tick)
        & (pl.col("tick") <= kill_tick)
    ).select(["tick"]).sort("tick")

    if s.is_empty():
        return None
    return int(s.row(0)[0])


def load_parquet_from_zip(z: zipfile.ZipFile, name: str) -> pl.DataFrame:
    return pl.read_parquet(io.BytesIO(z.read(name)))


def build_pair_tick_table(
    ticks: pl.DataFrame,
    attacker_id: int,
    victim_id: int,
    start_tick: int,
    end_tick: int,
) -> pl.DataFrame:
    keep = ["tick", "steamid", "X", "Y", "Z"]
    optional = [c for c in ["yaw", "pitch"] if c in ticks.columns]
    window = ticks.filter(
        (pl.col("tick") >= start_tick)
        & (pl.col("tick") <= end_tick)
        & (pl.col("steamid").is_in([attacker_id, victim_id]))
    ).select(keep + optional).sort(["tick", "steamid"])

    if window.is_empty():
        return pl.DataFrame()

    attacker_cols = ["tick", "aX", "aY", "aZ"]
    victim_cols = ["tick", "vX", "vY", "vZ"]
    rename_a = {"X": "aX", "Y": "aY", "Z": "aZ"}
    rename_v = {"X": "vX", "Y": "vY", "Z": "vZ"}
    if "yaw" in optional:
        rename_a["yaw"] = "a_yaw"
        attacker_cols.append("a_yaw")
        rename_v["yaw"] = "v_yaw"
        victim_cols.append("v_yaw")
    if "pitch" in optional:
        rename_a["pitch"] = "a_pitch"
        attacker_cols.append("a_pitch")
        rename_v["pitch"] = "v_pitch"
        victim_cols.append("v_pitch")

    attacker_ticks = (
        window.filter(pl.col("steamid") == attacker_id)
        .rename(rename_a)
        .select(attacker_cols)
    )
    victim_ticks = (
        window.filter(pl.col("steamid") == victim_id)
        .rename(rename_v)
        .select(victim_cols)
    )

    return attacker_ticks.join(victim_ticks, on="tick", how="inner").sort("tick")


def iter_pair_visibility(tv: pl.DataFrame, map_name: str) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for row in tv.iter_rows(named=True):
        p1 = Point3(float(row["aX"]), float(row["aY"]), float(row["aZ"]) + EYE_Z)
        p2 = Point3(float(row["vX"]), float(row["vY"]), float(row["vZ"]) + CHEST_Z)
        dx = float(row["vX"]) - float(row["aX"])
        dy = float(row["vY"]) - float(row["aY"])
        dz = float(row["vZ"] + CHEST_Z) - float(row["aZ"] + EYE_Z)
        distance = math.sqrt(dx * dx + dy * dy + dz * dz)
        tgt_yaw = math.degrees(math.atan2(dy, dx))
        horiz = math.hypot(dx, dy)
        tgt_pitch = -math.degrees(math.atan2(dz, horiz))

        a_yaw = _to_float(row.get("a_yaw"))
        a_pitch = _to_float(row.get("a_pitch"))
        aim_err = None
        if a_yaw is not None and a_pitch is not None:
            aim_err = aim_error_deg(a_yaw, a_pitch, dx, dy, dz)

        visible = False
        if distance <= MAX_LOS_DISTANCE:
            visible = is_visible(map_name, p1, p2)

        rows.append(
            {
                "tick": int(row["tick"]),
                "is_visible": visible,
                "distance": float(distance),
                "tgt_yaw": float(tgt_yaw),
                "tgt_pitch": float(tgt_pitch),
                "aim_error_deg": aim_err,
                "a_yaw": a_yaw,
                "a_pitch": a_pitch,
                "aX": float(row["aX"]),
                "aY": float(row["aY"]),
                "aZ": float(row["aZ"]),
                "vX": float(row["vX"]),
                "vY": float(row["vY"]),
                "vZ": float(row["vZ"]),
            }
        )
    return rows


def segment_visibility_encounters(vis_rows: list[dict[str, object]]) -> list[list[dict[str, object]]]:
    encounters: list[list[dict[str, object]]] = []
    n = len(vis_rows)
    idx = 0

    while idx < n:
        if not vis_rows[idx]["is_visible"]:
            idx += 1
            continue

        consec = 1
        run_end = idx
        while run_end + 1 < n and vis_rows[run_end + 1]["is_visible"]:
            run_end += 1
            consec += 1

        if consec < REQ_CONSEC:
            idx = run_end + 1
            continue

        start_idx = idx
        last_visible_idx = run_end
        timeout_tick = int(vis_rows[start_idx]["tick"]) + ENCOUNTER_TIMEOUT_TICKS
        j = run_end + 1

        while j < n:
            tick = int(vis_rows[j]["tick"])
            if tick > timeout_tick:
                break
            if vis_rows[j]["is_visible"]:
                last_visible_idx = j
            else:
                gap = tick - int(vis_rows[last_visible_idx]["tick"])
                if gap > ENCOUNTER_BREAK_TICKS:
                    break
            j += 1

        encounter = vis_rows[start_idx : last_visible_idx + 1]
        if any(row["is_visible"] for row in encounter):
            encounters.append(encounter)
        idx = max(last_visible_idx + 1, j)

    return encounters


def first_tick_with_aim_lock(encounter_rows: list[dict[str, object]], threshold_deg: float) -> int | None:
    for row in encounter_rows:
        aim_err = row.get("aim_error_deg")
        if row["is_visible"] and aim_err is not None and float(aim_err) <= float(threshold_deg):
            return int(row["tick"])
    return None


def _angular_motion_from_series(rows: list[dict[str, object]], yaw_key: str, pitch_key: str) -> dict[str, float | None]:
    values = [
        (int(row["tick"]), _to_float(row.get(yaw_key)), _to_float(row.get(pitch_key)))
        for row in rows
        if row["is_visible"] and _to_float(row.get(yaw_key)) is not None and _to_float(row.get(pitch_key)) is not None
    ]
    if len(values) < 2:
        return {
            "mean": None,
            "p90": None,
            "max": None,
            "std": None,
            "jerk_mean": None,
            "jerk_p90": None,
            "jerk_max": None,
        }

    velocities: list[float] = []
    jerks: list[float] = []
    prev_velocity: float | None = None
    prev_tick, prev_yaw, prev_pitch = values[0]

    for tick, yaw, pitch in values[1:]:
        if yaw is None or pitch is None:
            continue
        dt = max(1, tick - prev_tick)
        dyaw = wrap_deg(yaw - float(prev_yaw))
        dpitch = wrap_deg(pitch - float(prev_pitch))
        velocity = math.hypot(dyaw, dpitch) / dt
        velocities.append(float(velocity))
        if prev_velocity is not None:
            jerks.append(float(abs(velocity - prev_velocity) / dt))
        prev_velocity = velocity
        prev_tick, prev_yaw, prev_pitch = tick, yaw, pitch

    return {
        "mean": _mean(velocities),
        "p90": _quantile(velocities, 0.90),
        "max": max(velocities) if velocities else None,
        "std": _std(velocities),
        "jerk_mean": _mean(jerks),
        "jerk_p90": _quantile(jerks, 0.90),
        "jerk_max": max(jerks) if jerks else None,
    }


def compute_spatial_motion_stats(encounter_rows: list[dict[str, object]]) -> dict[str, float | None]:
    visible_rows = [row for row in encounter_rows if row["is_visible"]]
    if len(visible_rows) < 2:
        distances = [float(row["distance"]) for row in visible_rows]
        return {
            "distance_mean": _mean(distances),
            "distance_min": min(distances) if distances else None,
            "distance_p90": _quantile(distances, 0.90),
            "distance_max": max(distances) if distances else None,
            "distance_std": None,
            "closing_speed_mean": None,
            "closing_speed_p90": None,
            "closing_speed_max": None,
            "attacker_speed_mean": None,
            "attacker_speed_p90": None,
            "victim_speed_mean": None,
            "victim_speed_p90": None,
            "relative_speed_mean": None,
            "relative_speed_p90": None,
            "los_angular_velocity_mean": None,
            "los_angular_velocity_p90": None,
            "los_angular_velocity_max": None,
            "los_angular_jerk_mean": None,
            "los_angular_jerk_p90": None,
            "los_angular_jerk_max": None,
        }

    distances = [float(row["distance"]) for row in visible_rows]
    closing_speeds: list[float] = []
    attacker_speeds: list[float] = []
    victim_speeds: list[float] = []
    relative_speeds: list[float] = []

    prev = visible_rows[0]
    for row in visible_rows[1:]:
        dt = max(1, int(row["tick"]) - int(prev["tick"]))
        prev_dist = float(prev["distance"])
        cur_dist = float(row["distance"])
        closing_speeds.append(float((prev_dist - cur_dist) / dt))

        adx = float(row["aX"]) - float(prev["aX"])
        ady = float(row["aY"]) - float(prev["aY"])
        adz = float(row["aZ"]) - float(prev["aZ"])
        vdx = float(row["vX"]) - float(prev["vX"])
        vdy = float(row["vY"]) - float(prev["vY"])
        vdz = float(row["vZ"]) - float(prev["vZ"])
        attacker_speeds.append(float(math.sqrt(adx * adx + ady * ady + adz * adz) / dt))
        victim_speeds.append(float(math.sqrt(vdx * vdx + vdy * vdy + vdz * vdz) / dt))
        rdx = (float(row["vX"]) - float(row["aX"])) - (float(prev["vX"]) - float(prev["aX"]))
        rdy = (float(row["vY"]) - float(row["aY"])) - (float(prev["vY"]) - float(prev["aY"]))
        rdz = (float(row["vZ"]) - float(row["aZ"])) - (float(prev["vZ"]) - float(prev["aZ"]))
        relative_speeds.append(float(math.sqrt(rdx * rdx + rdy * rdy + rdz * rdz) / dt))
        prev = row

    los_motion = _angular_motion_from_series(visible_rows, "tgt_yaw", "tgt_pitch")
    return {
        "distance_mean": _mean(distances),
        "distance_min": min(distances) if distances else None,
        "distance_p90": _quantile(distances, 0.90),
        "distance_max": max(distances) if distances else None,
        "distance_std": _std(distances),
        "closing_speed_mean": _mean(closing_speeds),
        "closing_speed_p90": _quantile(closing_speeds, 0.90),
        "closing_speed_max": max(closing_speeds) if closing_speeds else None,
        "attacker_speed_mean": _mean(attacker_speeds),
        "attacker_speed_p90": _quantile(attacker_speeds, 0.90),
        "victim_speed_mean": _mean(victim_speeds),
        "victim_speed_p90": _quantile(victim_speeds, 0.90),
        "relative_speed_mean": _mean(relative_speeds),
        "relative_speed_p90": _quantile(relative_speeds, 0.90),
        "los_angular_velocity_mean": los_motion["mean"],
        "los_angular_velocity_p90": los_motion["p90"],
        "los_angular_velocity_max": los_motion["max"],
        "los_angular_jerk_mean": los_motion["jerk_mean"],
        "los_angular_jerk_p90": los_motion["jerk_p90"],
        "los_angular_jerk_max": los_motion["jerk_max"],
    }


def compute_encounter_row(
    demo_id: str,
    map_name: str,
    round_num: int,
    attacker_id: int,
    attacker_name: str | None,
    victim_id: int,
    victim_name: str | None,
    attacker_side: str | None,
    victim_side: str | None,
    encounter_rows: list[dict[str, object]],
    shot_ticks: list[int],
    damage_events: list[dict[str, object]],
    kill_events: list[dict[str, object]],
) -> dict[str, object]:
    start_tick = int(encounter_rows[0]["tick"])
    end_tick = int(encounter_rows[-1]["tick"])
    visible_rows = [row for row in encounter_rows if row["is_visible"]]
    visible_tick_count = len(visible_rows)
    exposure_duration = int(end_tick - start_tick + 1)
    occluded_ticks = max(0, exposure_duration - visible_tick_count)
    visible_ratio = (visible_tick_count / exposure_duration) if exposure_duration > 0 else None

    first_shot = _first_in_range(shot_ticks, start_tick, end_tick)
    encounter_shots = _slice_in_range(shot_ticks, start_tick, end_tick)
    encounter_damages = _events_in_range(damage_events, start_tick, end_tick)
    damage_count = len(encounter_damages)
    damage_total = float(
        sum(float(ev.get("dmg_health_real", ev.get("dmg_health", 0.0)) or 0.0) for ev in encounter_damages)
    )
    first_damage_tick = int(encounter_damages[0]["tick"]) if encounter_damages else None
    encounter_kills = _events_in_range(kill_events, start_tick, end_tick + KILL_WITHIN_TICKS)
    kill_tick = int(encounter_kills[0]["tick"]) if encounter_kills else None

    first_visible = visible_rows[0] if visible_rows else None
    aim_errors = [float(row["aim_error_deg"]) for row in visible_rows if row.get("aim_error_deg") is not None]
    aim_lock_tick = first_tick_with_aim_lock(encounter_rows, AIM_ACQUIRE_ERR_DEG)
    aim_motion = _angular_motion_from_series(encounter_rows, "a_yaw", "a_pitch")
    spatial_motion = compute_spatial_motion_stats(encounter_rows)
    shot_gaps = [encounter_shots[i] - encounter_shots[i - 1] for i in range(1, len(encounter_shots))]

    weapon = None
    if encounter_damages and encounter_damages[0].get("weapon") is not None:
        weapon = encounter_damages[0].get("weapon")
    elif encounter_kills and encounter_kills[0].get("weapon") is not None:
        weapon = encounter_kills[0].get("weapon")

    return {
        "demo_id": demo_id,
        "map_name": map_name,
        "round_num": int(round_num),
        "encounter_id": f"{demo_id}_{attacker_id}_{victim_id}_{start_tick}_{end_tick}",
        "attacker_steamid": int(attacker_id),
        "attacker_name": attacker_name,
        "victim_steamid": int(victim_id),
        "victim_name": victim_name,
        "attacker_side": attacker_side,
        "victim_side": victim_side,
        "start_tick": start_tick,
        "end_tick": end_tick,
        "exposure_duration": exposure_duration,
        "visible_tick_count": int(visible_tick_count),
        "occluded_tick_count": int(occluded_ticks),
        "visible_ratio": float(visible_ratio) if visible_ratio is not None else None,
        "time_to_first_shot": int(first_shot - start_tick) if first_shot is not None else None,
        "time_to_first_damage": int(first_damage_tick - start_tick) if first_damage_tick is not None else None,
        "aim_error_at_first_visible": float(first_visible["aim_error_deg"]) if first_visible is not None and first_visible.get("aim_error_deg") is not None else None,
        "aim_error_min": min(aim_errors) if aim_errors else None,
        "aim_error_p10": _quantile(aim_errors, 0.10),
        "aim_error_p90": _quantile(aim_errors, 0.90),
        "aim_acquire_time": int(aim_lock_tick - start_tick) if aim_lock_tick is not None else None,
        "aim_dwell_ticks": int(sum(1 for err in aim_errors if err <= AIM_ACQUIRE_ERR_DEG)) if aim_errors else None,
        "shot_before_aim_acquire": bool(first_shot is not None and aim_lock_tick is not None and first_shot < aim_lock_tick),
        "shot_count": int(len(encounter_shots)),
        "shot_rate_per_128": float((len(encounter_shots) * 128.0) / exposure_duration) if exposure_duration > 0 else None,
        "mean_shot_gap": _mean([float(v) for v in shot_gaps]),
        "damage_count": int(damage_count),
        "damage_total": damage_total,
        "ended_in_damage": bool(damage_count > 0),
        "ended_in_kill_within_y": kill_tick is not None,
        "kill_tick": int(kill_tick) if kill_tick is not None else None,
        "weapon": weapon,
        "angular_velocity_mean": aim_motion["mean"],
        "angular_velocity_p90": aim_motion["p90"],
        "angular_velocity_max": aim_motion["max"],
        "angular_velocity_std": aim_motion["std"],
        "angular_jerk_mean": aim_motion["jerk_mean"],
        "angular_jerk_p90": aim_motion["jerk_p90"],
        "angular_jerk_max": aim_motion["jerk_max"],
        **spatial_motion,
    }


def empty_encounter_frame() -> pl.DataFrame:
    return pl.DataFrame(
        schema={
            "demo_id": pl.Utf8,
            "map_name": pl.Utf8,
            "round_num": pl.Int64,
            "encounter_id": pl.Utf8,
            "attacker_steamid": pl.Int64,
            "attacker_name": pl.Utf8,
            "victim_steamid": pl.Int64,
            "victim_name": pl.Utf8,
            "attacker_side": pl.Utf8,
            "victim_side": pl.Utf8,
            "start_tick": pl.Int64,
            "end_tick": pl.Int64,
            "exposure_duration": pl.Int64,
            "visible_tick_count": pl.Int64,
            "occluded_tick_count": pl.Int64,
            "visible_ratio": pl.Float64,
            "time_to_first_shot": pl.Int64,
            "time_to_first_damage": pl.Int64,
            "aim_error_at_first_visible": pl.Float64,
            "aim_error_min": pl.Float64,
            "aim_error_p10": pl.Float64,
            "aim_error_p90": pl.Float64,
            "aim_acquire_time": pl.Int64,
            "aim_dwell_ticks": pl.Int64,
            "shot_before_aim_acquire": pl.Boolean,
            "shot_count": pl.Int64,
            "shot_rate_per_128": pl.Float64,
            "mean_shot_gap": pl.Float64,
            "damage_count": pl.Int64,
            "damage_total": pl.Float64,
            "ended_in_damage": pl.Boolean,
            "ended_in_kill_within_y": pl.Boolean,
            "kill_tick": pl.Int64,
            "weapon": pl.Utf8,
            "angular_velocity_mean": pl.Float64,
            "angular_velocity_p90": pl.Float64,
            "angular_velocity_max": pl.Float64,
            "angular_velocity_std": pl.Float64,
            "angular_jerk_mean": pl.Float64,
            "angular_jerk_p90": pl.Float64,
            "angular_jerk_max": pl.Float64,
            "distance_mean": pl.Float64,
            "distance_min": pl.Float64,
            "distance_p90": pl.Float64,
            "distance_max": pl.Float64,
            "distance_std": pl.Float64,
            "closing_speed_mean": pl.Float64,
            "closing_speed_p90": pl.Float64,
            "closing_speed_max": pl.Float64,
            "attacker_speed_mean": pl.Float64,
            "attacker_speed_p90": pl.Float64,
            "victim_speed_mean": pl.Float64,
            "victim_speed_p90": pl.Float64,
            "relative_speed_mean": pl.Float64,
            "relative_speed_p90": pl.Float64,
            "los_angular_velocity_mean": pl.Float64,
            "los_angular_velocity_p90": pl.Float64,
            "los_angular_velocity_max": pl.Float64,
            "los_angular_jerk_mean": pl.Float64,
            "los_angular_jerk_p90": pl.Float64,
            "los_angular_jerk_max": pl.Float64,
        }
    )


def build_encounters_for_zip(
    zip_path: Path,
    map_name: str,
    ticks: pl.DataFrame,
    shots: pl.DataFrame,
    kills: pl.DataFrame,
    damages: pl.DataFrame,
) -> pl.DataFrame:
    demo_id = zip_path.stem
    rows: list[dict[str, object]] = []

    tick_cols = ["tick", "round_num", "steamid", "name", "side", "X", "Y", "Z"]
    tick_optional = [c for c in ["yaw", "pitch"] if c in ticks.columns]
    base_ticks = (
        ticks.select([c for c in tick_cols + tick_optional if c in ticks.columns])
        .filter(
            pl.col("steamid").is_not_null()
            & pl.col("tick").is_not_null()
            & pl.col("round_num").is_not_null()
        )
        .sort(["round_num", "tick", "steamid"])
    )

    round_ticks: dict[int, pl.DataFrame] = {}
    player_meta: dict[tuple[int, int], dict[str, object]] = {}
    for round_num in base_ticks.get_column("round_num").unique().to_list():
        rnd = int(round_num)
        df_round = base_ticks.filter(pl.col("round_num") == rnd)
        round_ticks[rnd] = df_round

        meta_df = (
            df_round.group_by("steamid")
            .agg(
                [
                    pl.col("name").drop_nulls().last().alias("name"),
                    pl.col("side").drop_nulls().last().alias("side"),
                ]
            )
            .sort("steamid")
        )
        for rec in meta_df.iter_rows(named=True):
            sid = rec.get("steamid")
            if sid is None:
                continue
            player_meta[(rnd, int(sid))] = {
                "name": rec.get("name"),
                "side": str(rec.get("side") or "").lower(),
            }

    shot_ticks_by_round_attacker: dict[tuple[int, int], list[int]] = {}
    if not shots.is_empty():
        for row in shots.select(["round_num", "player_steamid", "tick"]).iter_rows(named=True):
            rnd = row.get("round_num")
            sid = row.get("player_steamid")
            tick = row.get("tick")
            if rnd is None or sid is None or tick is None:
                continue
            shot_ticks_by_round_attacker.setdefault((int(rnd), int(sid)), []).append(int(tick))
    for values in shot_ticks_by_round_attacker.values():
        values.sort()

    damage_events_by_pair: dict[tuple[int, int, int], list[dict[str, object]]] = {}
    if not damages.is_empty():
        damage_cols = [c for c in ["round_num", "attacker_steamid", "victim_steamid", "tick", "weapon", "dmg_health", "dmg_health_real"] if c in damages.columns]
        for row in damages.select(damage_cols).iter_rows(named=True):
            rnd = row.get("round_num")
            attacker = row.get("attacker_steamid")
            victim = row.get("victim_steamid")
            tick = row.get("tick")
            if rnd is None or attacker is None or victim is None or tick is None:
                continue
            damage_events_by_pair.setdefault((int(rnd), int(attacker), int(victim)), []).append(
                {
                    "tick": int(tick),
                    "weapon": row.get("weapon"),
                    "dmg_health": row.get("dmg_health"),
                    "dmg_health_real": row.get("dmg_health_real"),
                }
            )
    for values in damage_events_by_pair.values():
        values.sort(key=lambda x: int(x["tick"]))

    kill_events_by_pair: dict[tuple[int, int, int], list[dict[str, object]]] = {}
    for row in kills.select(["round_num", "attacker_steamid", "victim_steamid", "tick", "weapon"]).iter_rows(named=True):
        rnd = row.get("round_num")
        attacker = row.get("attacker_steamid")
        victim = row.get("victim_steamid")
        tick = row.get("tick")
        if rnd is None or attacker is None or victim is None or tick is None:
            continue
        kill_events_by_pair.setdefault((int(rnd), int(attacker), int(victim)), []).append(
            {"tick": int(tick), "weapon": row.get("weapon")}
        )
    for values in kill_events_by_pair.values():
        values.sort(key=lambda x: int(x["tick"]))

    for round_num, ticks_round in round_ticks.items():
        round_players = sorted(
            {
                int(row["steamid"])
                for row in ticks_round.select(["steamid"]).unique().iter_rows(named=True)
                if row.get("steamid") is not None
            }
        )
        if len(round_players) < 2:
            continue

        start_tick = int(ticks_round["tick"].min())
        end_tick = int(ticks_round["tick"].max())

        for attacker_id in round_players:
            attacker_meta = player_meta.get((round_num, attacker_id), {})
            attacker_side = str(attacker_meta.get("side") or "").lower()
            if attacker_side not in {"ct", "t"}:
                continue

            for victim_id in round_players:
                if victim_id == attacker_id:
                    continue
                victim_meta = player_meta.get((round_num, victim_id), {})
                victim_side = str(victim_meta.get("side") or "").lower()
                if victim_side not in {"ct", "t"} or victim_side == attacker_side:
                    continue

                tv = build_pair_tick_table(
                    ticks=ticks_round,
                    attacker_id=attacker_id,
                    victim_id=victim_id,
                    start_tick=start_tick,
                    end_tick=end_tick,
                )
                if tv.is_empty():
                    continue

                vis_rows = iter_pair_visibility(tv, map_name)
                for encounter_rows in segment_visibility_encounters(vis_rows):
                    rows.append(
                        compute_encounter_row(
                            demo_id=demo_id,
                            map_name=map_name,
                            round_num=round_num,
                            attacker_id=attacker_id,
                            attacker_name=attacker_meta.get("name"),
                            victim_id=victim_id,
                            victim_name=victim_meta.get("name"),
                            attacker_side=attacker_side,
                            victim_side=victim_side,
                            encounter_rows=encounter_rows,
                            shot_ticks=shot_ticks_by_round_attacker.get((round_num, attacker_id), []),
                            damage_events=damage_events_by_pair.get((round_num, attacker_id, victim_id), []),
                            kill_events=kill_events_by_pair.get((round_num, attacker_id, victim_id), []),
                        )
                    )

    if not rows:
        return empty_encounter_frame()
    return pl.DataFrame(rows).sort(["round_num", "start_tick", "attacker_steamid", "victim_steamid"])


def build_kill_features_for_zip(
    zip_path: Path,
    map_name: str,
    ticks: pl.DataFrame,
    kills: pl.DataFrame,
    shots: pl.DataFrame,
) -> pl.DataFrame:
    demo_id = zip_path.stem
    rows = []
    for k in kills.iter_rows(named=True):
        a_raw = k.get("attacker_steamid")
        v_raw = k.get("victim_steamid")
        t_raw = k.get("tick")

        if a_raw is None or v_raw is None or t_raw is None:
            continue

        attacker = int(a_raw)
        victim = int(v_raw)
        kt = int(t_raw)
        round_num = int(k.get("round_num", -1))

        t0 = first_visible_tick_los(ticks, map_name, attacker, victim, kt)

        pre_start = max(0, kt - W_PRE)
        fs = first_shot_tick(shots, attacker, pre_start, kt)
        rt = None
        if t0 is not None and fs is not None:
            rt = int(fs - t0)

        shots_64 = shots.filter(
            (pl.col("player_steamid") == attacker)
            & (pl.col("tick") >= kt - 64)
            & (pl.col("tick") <= kt)
        ).height

        shots_128 = shots.filter(
            (pl.col("player_steamid") == attacker)
            & (pl.col("tick") >= kt - 128)
            & (pl.col("tick") <= kt)
        ).height

        vis_before_shot = (fs - t0) if (t0 is not None and fs is not None) else None
        vis_before_kill = (kt - t0) if (t0 is not None) else None

        is_mp4 = vis_before_shot is not None and vis_before_shot <= 4
        is_mp6 = vis_before_shot is not None and vis_before_shot <= 6
        is_mp8 = vis_before_shot is not None and vis_before_shot <= 8
        is_prefire = rt is not None and rt <= -2
        is_thrusmoke = bool(k.get("thrusmoke", False))
        is_long_range_fast_rt_4 = (
            rt is not None
            and k.get("distance") is not None
            and float(k.get("distance")) >= LONG_RANGE_DIST
            and int(rt) <= 4
        )

        rows.append(
            {
                "demo_id": demo_id,
                "map_name": map_name,
                "round_num": round_num,
                "kill_tick": kt,
                "t0_visible": t0,
                "first_shot_tick": fs,
                "rt_ticks": rt,
                "attacker_steamid": attacker,
                "attacker_name": k.get("attacker_name"),
                "victim_steamid": victim,
                "victim_name": k.get("victim_name"),
                "weapon": k.get("weapon"),
                "headshot": bool(k.get("headshot", False)),
                "distance": float(k.get("distance", 0.0)) if k.get("distance") is not None else None,
                "visible_ticks_before_shot": vis_before_shot,
                "visible_ticks_before_kill": vis_before_kill,
                "shots_last64_before_kill": shots_64,
                "shots_last128_before_kill": shots_128,
                "is_micropeek_4": is_mp4,
                "is_micropeek_6": is_mp6,
                "is_micropeek_8": is_mp8,
                "is_prefire": is_prefire,
                "is_thrusmoke": is_thrusmoke,
                "is_long_range_fast_rt_4": is_long_range_fast_rt_4,
            }
        )

    return pl.DataFrame(rows)


def build_for_zip(zip_path: Path) -> tuple[pl.DataFrame, pl.DataFrame]:
    map_name = map_name_from_zip(zip_path)
    with zipfile.ZipFile(zip_path, "r") as z:
        ticks = load_parquet_from_zip(z, "ticks.parquet")
        kills = load_parquet_from_zip(z, "kills.parquet")
        shots = load_parquet_from_zip(z, "shots.parquet")
        damages = load_parquet_from_zip(z, "damages.parquet") if "damages.parquet" in z.namelist() else pl.DataFrame()

    kill_df = build_kill_features_for_zip(zip_path, map_name, ticks, kills, shots)
    encounter_df = build_encounters_for_zip(zip_path, map_name, ticks, shots, kills, damages)
    return kill_df, encounter_df


def _process_one_zip(zip_path_str: str) -> tuple[str, bool, str]:
    zp = Path(zip_path_str)
    demo_id = zp.stem
    out_dir = OUT_ROOT / demo_id
    out_dir.mkdir(parents=True, exist_ok=True)
    kill_out_path = out_dir / "engagement_features.parquet"
    encounter_out_path = out_dir / "encounters.parquet"
    try:
        kill_df, encounter_df = build_for_zip(zp)
        kill_df.write_parquet(kill_out_path)
        encounter_df.write_parquet(encounter_out_path)
        return demo_id, True, ""
    except Exception as exc:
        return demo_id, False, str(exc)


def main():
    args = parse_args()
    zips = sorted(ZIPS_DIR.glob("*.zip"))
    if args.max_demos is not None:
        zips = zips[: int(args.max_demos)]

    OUT_ROOT.mkdir(parents=True, exist_ok=True)

    pending: list[Path] = []
    skipped = 0
    for zp in zips:
        demo_id = zp.stem
        out_dir = OUT_ROOT / demo_id
        out_dir.mkdir(parents=True, exist_ok=True)
        kill_out_path = out_dir / "engagement_features.parquet"
        encounter_out_path = out_dir / "encounters.parquet"
        if not args.overwrite and outputs_current(kill_out_path, encounter_out_path):
            print(f"[SKIP] {demo_id} -> current outputs already present")
            skipped += 1
            continue
        pending.append(zp)

    if not pending:
        print(f"Done. OK=0, FAIL=0, SKIP={skipped}, out_root={OUT_ROOT}")
        return

    ok = 0
    fail = 0
    workers = max(1, int(args.workers))
    print(f"[INFO] demos_total={len(zips)} pending={len(pending)} workers={workers} skipped={skipped}")

    if workers == 1:
        for zp in pending:
            demo_id = zp.stem
            print(f"[BUILD] {demo_id}")
            demo_id, success, message = _process_one_zip(str(zp))
            if success:
                print(f"[OK]   {demo_id}")
                ok += 1
            else:
                print(f"[FAIL] {demo_id}: {message}")
                fail += 1
    else:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(_process_one_zip, str(zp)): zp.stem for zp in pending}
            for future in as_completed(futures):
                demo_id = futures[future]
                try:
                    demo_id, success, message = future.result()
                except Exception as exc:
                    print(f"[FAIL] {demo_id}: {exc}")
                    fail += 1
                    continue
                if success:
                    print(f"[OK]   {demo_id}")
                    ok += 1
                else:
                    print(f"[FAIL] {demo_id}: {message}")
                    fail += 1

    print(f"Done. OK={ok}, FAIL={fail}, SKIP={skipped}, out_root={OUT_ROOT}")


if __name__ == "__main__":
    main()

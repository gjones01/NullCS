from __future__ import annotations

from importlib import metadata
from pathlib import Path
import sys
from typing import Mapping

import pandas as pd
from demoparser2 import DemoParser

MAIN_ROOT = Path(__file__).resolve().parents[2]
if str(MAIN_ROOT) not in sys.path:
    sys.path.insert(0, str(MAIN_ROOT))

from src.adapters.cs2cd_adapter import CS2CDMatch


CRITICAL_TICK_COLUMNS = {
    "tick",
    "steamid",
    "X",
    "Y",
    "Z",
    "yaw",
    "pitch",
    "is_alive",
    "team_num",
}

# Tick props that reach model/report inputs. Verified 2026-09-30 against the
# 449-feature XGB contract (active_weapon_name -> weapon_entropy /
# dominant_weapon_share; is_walking -> enc_walking_*; is_airborne ->
# enc_airborne_*) and the 35 NN temporal channels (a_mdx/a_mdy,
# cmd_pitch_delta/cmd_yaw_delta, a_scoped, a_flashed, v_spotted, a_walking,
# a_airborne, attacker_speed/relative_speed from velocity_*).
#
# demoparser2 is silent about unknown props, and CS2 sendtable churn removes and
# renames them between patches (14135 -> 14153 dropped 53 fields, including
# CCSPlayer_WeaponServices.m_bIsLookingAtWeapon). Without this guard a dropped
# model prop is zero-filled from DEFAULT_TICK_COLUMNS and the score changes with
# no warning, so _ticks_table() refuses to score the demo instead.
MODEL_TICK_COLUMNS = frozenset(
    {
        "active_weapon_name",
        "flash_duration",
        "is_airborne",
        "is_scoped",
        "is_walking",
        "spotted",
        "usercmd_mouse_dx",
        "usercmd_mouse_dy",
        "usercmd_viewangle_x",
        "usercmd_viewangle_y",
        "velocity_X",
        "velocity_Y",
        "velocity_Z",
    }
)

DEFAULT_TICK_COLUMNS: dict[str, object] = {
    "name": "",
    "team_name": "",
    "active_weapon_name": "",
    "health": 100,
    "is_scoped": False,
    "flash_duration": 0.0,
    "is_walking": False,
    "is_airborne": False,
    "spotted": False,
    "move_collide": 0,
    "move_type": 0,
    "looking_at_weapon": False,
    "holding_look_at_weapon": False,
    "buttons": 0,
    "usercmd_mouse_dx": 0.0,
    "usercmd_mouse_dy": 0.0,
    "usercmd_viewangle_x": 0.0,
    "usercmd_viewangle_y": 0.0,
    "velocity_X": 0.0,
    "velocity_Y": 0.0,
    "velocity_Z": 0.0,
}

# Props requested from demoparser2 for every tick table, in one place so the parser
# contract can be probed by the smoke check (main/scripts/check_parser_contract.py)
# against exactly what production asks for. "tick"/"steamid" are always returned by
# demoparser2 and are not listed here.
WANTED_TICK_PROPS: tuple[str, ...] = (
    "X",
    "Y",
    "Z",
    "yaw",
    "pitch",
    "health",
    "is_alive",
    "team_num",
    "team_name",
    "active_weapon_name",
    "is_scoped",
    "flash_duration",
    "is_walking",
    "is_airborne",
    "spotted",
    "move_collide",
    "move_type",
    "looking_at_weapon",
    "holding_look_at_weapon",
    "buttons",
    "usercmd_mouse_dx",
    "usercmd_mouse_dy",
    "usercmd_viewangle_x",
    "usercmd_viewangle_y",
    "velocity_X",
    "velocity_Y",
    "velocity_Z",
)

_UNREQUESTED_TICK_COLUMNS = sorted(set(DEFAULT_TICK_COLUMNS).difference({"name"}, WANTED_TICK_PROPS))
if _UNREQUESTED_TICK_COLUMNS:
    raise RuntimeError(
        "DEFAULT_TICK_COLUMNS entries demoparser2 is never asked for would be zero-filled from a "
        f"value no demo can override: {_UNREQUESTED_TICK_COLUMNS}"
    )

# Everything that is not a model input is decorative: it is rendered/reported but
# never scored, so a missing one stays lenient (zero-filled with a [WARN] naming it).
DECORATIVE_TICK_COLUMNS: dict[str, object] = {
    key: default for key, default in DEFAULT_TICK_COLUMNS.items() if key not in MODEL_TICK_COLUMNS
}

_UNBACKED_MODEL_TICK_COLUMNS = sorted(MODEL_TICK_COLUMNS.difference(DEFAULT_TICK_COLUMNS))
if _UNBACKED_MODEL_TICK_COLUMNS:
    raise RuntimeError(
        "MODEL_TICK_COLUMNS entries without a DEFAULT_TICK_COLUMNS fallback would break the "
        f"decorative zero-fill loop: {_UNBACKED_MODEL_TICK_COLUMNS}"
    )

# Header fields stamped into infer artifacts as parser provenance.
PROVENANCE_HEADER_KEYS = ("patch_version", "demo_version_name", "demo_version_guid", "map_name")


def _col(df: pd.DataFrame, name: str, default: object) -> pd.Series:
    if name in df.columns:
        return df[name]
    return pd.Series(default, index=df.index)


def package_version(name: str) -> str | None:
    try:
        return metadata.version(name)
    except metadata.PackageNotFoundError:
        return None


def parser_provenance(header: Mapping[str, object] | None = None) -> dict[str, object]:
    """Provenance for one demoparser2-parsed demo: CS2 patch/build + the parser version.

    Recorded because neither the CS2 patch nor the demoparser2 build was stamped
    anywhere before, so a stored score could not be traced back to a suspect parser.
    """
    out: dict[str, object] = {"demoparser2_version": package_version("demoparser2")}
    for key in PROVENANCE_HEADER_KEYS:
        value = (header or {}).get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            out[key] = text
    return out


def _safe_event(parser: DemoParser, event_name: str) -> pd.DataFrame:
    try:
        df = parser.parse_event(event_name)
        return df if isinstance(df, pd.DataFrame) else pd.DataFrame(df)
    except Exception as exc:
        print(f"[WARN] demoparser2 could not parse event {event_name}: {exc}")
        return pd.DataFrame()


def _round_table(round_starts: pd.DataFrame, round_ends: pd.DataFrame) -> pd.DataFrame:
    starts = sorted(int(x) for x in round_starts.get("tick", pd.Series(dtype="int64")).dropna().tolist())
    ends = sorted(int(x) for x in round_ends.get("tick", pd.Series(dtype="int64")).dropna().tolist())
    n = max(len(starts), len(ends))
    return pd.DataFrame(
        [
            {
                "round_num": i + 1,
                "start_tick": starts[i] if i < len(starts) else None,
                "end_tick": ends[i] if i < len(ends) else None,
            }
            for i in range(n)
        ]
    )


def _assign_round_num(tick: int, round_starts: list[int]) -> int:
    if not round_starts:
        return 1
    lo, hi = 0, len(round_starts)
    while lo < hi:
        mid = (lo + hi) // 2
        if round_starts[mid] <= tick:
            lo = mid + 1
        else:
            hi = mid
    return max(1, lo)


def _kills_table(df: pd.DataFrame, round_starts: list[int], map_name: str) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(
            columns=["kill_tick", "round_num", "attacker_steamid", "victim_steamid", "headshot", "weapon", "distance", "is_thrusmoke", "map_name"]
        )
    out = df.copy()
    out["kill_tick"] = pd.to_numeric(_col(out, "tick", None), errors="coerce").astype("Int64")
    out = out[out["kill_tick"].notna()].copy()
    out["round_num"] = out["kill_tick"].astype(int).apply(lambda t: _assign_round_num(int(t), round_starts))
    out["attacker_steamid"] = _col(out, "attacker_steamid", "").astype(str).str.strip()
    out["victim_steamid"] = _col(out, "user_steamid", "").astype(str).str.strip()
    out["headshot"] = _col(out, "headshot", False).fillna(False).astype(bool)
    out["weapon"] = _col(out, "weapon", "").astype(str)
    out["distance"] = pd.to_numeric(_col(out, "distance", None), errors="coerce")
    out["is_thrusmoke"] = _col(out, "thrusmoke", False).fillna(False).astype(bool)
    out["map_name"] = map_name
    return out[["kill_tick", "round_num", "attacker_steamid", "victim_steamid", "headshot", "weapon", "distance", "is_thrusmoke", "map_name"]].reset_index(drop=True)


def _shots_table(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["shot_tick", "attacker_steamid", "weapon"])
    out = df.copy()
    out["shot_tick"] = pd.to_numeric(_col(out, "tick", None), errors="coerce").astype("Int64")
    out["attacker_steamid"] = _col(out, "user_steamid", "").astype(str).str.strip()
    out["weapon"] = _col(out, "weapon", "").astype(str).str.lower()
    out = out[out["shot_tick"].notna() & (out["attacker_steamid"] != "")].copy()
    out = out[~out["weapon"].str.contains("grenade", na=False)].copy()
    return out[["shot_tick", "attacker_steamid", "weapon"]].reset_index(drop=True)


def _damages_table(df: pd.DataFrame, round_starts: list[int]) -> pd.DataFrame:
    cols = [
        "tick",
        "round_num",
        "attacker_steamid",
        "victim_steamid",
        "distance",
        "in_air",
        "no_scope",
        "num_penetrations",
        "damage_dir_x",
        "damage_dir_y",
        "damage_dir_z",
    ]
    if df.empty:
        return pd.DataFrame(columns=cols)
    out = df.copy()
    out["tick"] = pd.to_numeric(_col(out, "tick", None), errors="coerce").astype("Int64")
    out = out[out["tick"].notna()].copy()
    out["round_num"] = out["tick"].astype(int).apply(lambda t: _assign_round_num(int(t), round_starts))
    out["attacker_steamid"] = _col(out, "attacker_steamid", "").astype(str).str.strip()
    out["victim_steamid"] = _col(out, "victim_steamid", "").astype(str).str.strip()
    out["distance"] = pd.to_numeric(_col(out, "distance", None), errors="coerce")
    out["in_air"] = _col(out, "in_air", False).fillna(False).astype(bool)
    out["no_scope"] = _col(out, "no_scope", False).fillna(False).astype(bool)
    out["num_penetrations"] = pd.to_numeric(_col(out, "num_penetrations", 0), errors="coerce").fillna(0).astype(int)
    for col in ["damage_dir_x", "damage_dir_y", "damage_dir_z"]:
        out[col] = pd.to_numeric(_col(out, col, None), errors="coerce")
    return out[cols].reset_index(drop=True)


def _ticks_table(parser: DemoParser) -> pd.DataFrame:
    df = parser.parse_ticks(list(WANTED_TICK_PROPS))
    out = df if isinstance(df, pd.DataFrame) else pd.DataFrame(df)
    if out.empty:
        raise RuntimeError("demoparser2 returned no tick rows; refusing to score this demo")
    missing = sorted(CRITICAL_TICK_COLUMNS.difference(out.columns))
    if missing:
        raise RuntimeError(
            "demoparser2 tick schema is missing required columns "
            f"{missing}; update the adapter before scoring this demo"
        )
    missing_model = sorted(MODEL_TICK_COLUMNS.difference(out.columns))
    if missing_model:
        raise RuntimeError(
            "demoparser2 tick schema is missing model-input columns "
            f"{missing_model}; refusing to score this demo. "
            "A CS2 patch removed or renamed a sendtable prop that feeds the feature "
            "contract, and zero-filling it would change the score silently. Confirm the "
            "demo's patch_version and re-check the prop names (demoparser2 "
            "list_updated_fields) before scoring."
        )
    dropped_decorative = sorted(col for col in DECORATIVE_TICK_COLUMNS if col not in out.columns)
    if dropped_decorative:
        print(
            "[WARN] demoparser2 omitted decorative tick columns "
            f"{dropped_decorative}; zero-filling them (rendered only, not model inputs)"
        )
    for col, default in DECORATIVE_TICK_COLUMNS.items():
        if col not in out.columns:
            out[col] = default
    out["steamid"] = out["steamid"].astype(str).str.strip()
    out = out[out["steamid"] != ""].copy()
    if out.empty:
        raise RuntimeError("demoparser2 tick rows did not contain usable SteamIDs; refusing to score this demo")
    return out.reset_index(drop=True)


def load_demo(demo_path: str | Path, demo_id: str) -> CS2CDMatch:
    path = Path(demo_path)
    parser = DemoParser(str(path))
    header = parser.parse_header()
    map_name = str(header.get("map_name", "unknown_map"))
    provenance = parser_provenance(header)

    round_starts = _safe_event(parser, "round_freeze_end")
    round_ends = _safe_event(parser, "round_officially_ended")
    rounds = _round_table(round_starts, round_ends)
    round_start_ticks = [int(x) for x in rounds["start_tick"].dropna().tolist()] if not rounds.empty else []

    kills_raw = _safe_event(parser, "player_death")
    shots_raw = _safe_event(parser, "weapon_fire")
    damages_raw = _safe_event(parser, "bullet_damage")
    ticks_df = _ticks_table(parser)

    kills = _kills_table(kills_raw, round_start_ticks, map_name)
    damages = _damages_table(damages_raw, round_start_ticks)
    shots = _shots_table(shots_raw)

    return CS2CDMatch(
        split="infer",
        match_id=demo_id,
        demo_id=demo_id,
        ticks_df=ticks_df,
        events_json={},
        map_name=map_name,
        cheater_ids=set(),
        kills=kills,
        damages=damages,
        shots=shots,
        rounds=rounds,
        parser_provenance=provenance,
    )

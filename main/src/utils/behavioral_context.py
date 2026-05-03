from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd

from .project_paths import DEMOS_ROOT

LONG_RANGE_DIST = 1500.0
LAPLACE_ALPHA = 1.0


def _clamp01(value: float | int | None) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except Exception:
        return 0.0


def _safe_float(value, default: float | None = None) -> float | None:
    try:
        if pd.isna(value):
            return default
    except Exception:
        pass
    try:
        return float(value)
    except Exception:
        return default


def _laplace(success: float, trials: float, alpha: float = LAPLACE_ALPHA) -> float:
    if trials <= 0:
        return 0.0
    return float((success + alpha) / (trials + (2.0 * alpha)))


def _normalized_entropy(counts: pd.Series) -> float:
    counts = pd.to_numeric(counts, errors="coerce").fillna(0.0)
    counts = counts[counts > 0]
    if counts.empty or len(counts) <= 1:
        return 0.0
    probs = counts / counts.sum()
    entropy = float(-(probs * np.log(probs)).sum())
    return _clamp01(entropy / math.log(len(probs)))


def _percentile_series(series: pd.Series, *, ascending: bool = True) -> pd.Series:
    vals = pd.to_numeric(series, errors="coerce")
    out = pd.Series(np.nan, index=series.index, dtype=float)
    mask = vals.notna()
    if mask.sum() == 0:
        return out
    out.loc[mask] = vals.loc[mask].rank(method="average", pct=True, ascending=ascending).astype(float)
    return out


def _series_or_default(df: pd.DataFrame, column: str, default) -> pd.Series:
    if column in df.columns:
        return df[column]
    return pd.Series(default, index=df.index)


def _weapon_family(value: object) -> str:
    w = str(value or "").lower().strip()
    rifles = {"ak47", "m4a1", "m4a1_silencer", "famas", "galilar", "aug", "sg556"}
    pistols = {"glock", "hkp2000", "usp_silencer", "p250", "elite", "fiveseven", "tec9", "cz75a", "deagle", "revolver"}
    awp_smg = {"awp", "ssg08", "mac10", "mp9", "mp7", "mp5sd", "ump45", "p90", "bizon"}
    if w in rifles:
        return "rifle"
    if w in pistols:
        return "pistol"
    if w in awp_smg:
        return "awp_smg"
    return "other"


def load_demo_frames(demo_id: str, demos_root: Path | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    root = demos_root or DEMOS_ROOT
    demo_dir = Path(root) / str(demo_id)
    eng_path = demo_dir / "engagement_features.parquet"
    if not eng_path.exists():
        raise FileNotFoundError(f"Missing engagement features: {eng_path}")
    eng = pd.read_parquet(eng_path).copy()
    enc_path = demo_dir / "encounters.parquet"
    enc = pd.read_parquet(enc_path).copy() if enc_path.exists() else pd.DataFrame()
    return eng, enc


def _kill_summary(eng: pd.DataFrame) -> pd.DataFrame:
    if eng.empty:
        return pd.DataFrame()

    work = eng.copy()
    work["attacker_steamid"] = work["attacker_steamid"].astype(str).str.strip()
    work["victim_steamid"] = work["victim_steamid"].astype(str).str.strip()
    work["weapon_family"] = _series_or_default(work, "weapon", "").map(_weapon_family)
    work["rt_ticks"] = pd.to_numeric(work.get("rt_ticks"), errors="coerce")
    work["distance"] = pd.to_numeric(work.get("distance"), errors="coerce")
    work["headshot"] = _series_or_default(work, "headshot", False).fillna(False).astype(bool)
    work["is_prefire"] = _series_or_default(work, "is_prefire", False).fillna(False).astype(bool)
    work["is_thrusmoke"] = _series_or_default(work, "is_thrusmoke", False).fillna(False).astype(bool)
    work["is_long_range_fast_rt_4"] = _series_or_default(work, "is_long_range_fast_rt_4", False).fillna(False).astype(bool)
    work["is_micropeek_4"] = _series_or_default(work, "is_micropeek_4", False).fillna(False).astype(bool)
    work["round_num"] = pd.to_numeric(work.get("round_num"), errors="coerce")

    demo_victim_kills = work.groupby(["demo_id", "victim_steamid"]).size().rename("victim_demo_deaths").reset_index()
    demo_attacker_kills = work.groupby(["demo_id", "attacker_steamid"]).size().rename("player_demo_kills").reset_index()
    victim_strength = demo_attacker_kills.rename(columns={"attacker_steamid": "victim_steamid", "player_demo_kills": "victim_demo_kills"})
    work = work.merge(victim_strength, on=["demo_id", "victim_steamid"], how="left")
    work["victim_demo_kills"] = work["victim_demo_kills"].fillna(0.0)

    rows: list[dict[str, object]] = []
    for (demo_id, steamid), g in work.groupby(["demo_id", "attacker_steamid"], sort=False):
        n_kills = int(len(g))
        rt = g["rt_ticks"].dropna()
        rt_n = int(len(rt))
        rounds = g["round_num"].dropna().astype(int)
        round_counts = rounds.value_counts()
        weapon_counts = g["weapon_family"].value_counts()
        victim_counts = g["victim_steamid"].value_counts()
        signal_mask = g["is_prefire"] | g["is_thrusmoke"] | g["is_long_range_fast_rt_4"] | g["is_micropeek_4"]
        signal_round_counts = g.loc[signal_mask, "round_num"].dropna().astype(int).value_counts()
        long_range_mask = g["distance"].fillna(-1) >= LONG_RANGE_DIST

        rounds_with_kills = int(round_counts.shape[0])
        top_round_share = float(round_counts.max() / n_kills) if n_kills else 0.0
        top_signal_round_share = float(signal_round_counts.max() / max(1, int(signal_mask.sum()))) if int(signal_mask.sum()) else 0.0
        dominant_weapon_share = float(weapon_counts.max() / n_kills) if n_kills else 0.0
        top_victim_share = float(victim_counts.max() / n_kills) if n_kills else 0.0

        row = {
            "demo_id": str(demo_id),
            "attacker_steamid": str(steamid),
            "attacker_name": str(g.get("attacker_name", pd.Series([""])).iloc[0]),
            "n_kills": n_kills,
            "rt_n": rt_n,
            "rounds_with_kills": rounds_with_kills,
            "round_kill_entropy": _normalized_entropy(round_counts),
            "top_round_kill_share": round(top_round_share, 6),
            "multi_kill_round_rate": _laplace(float((round_counts >= 2).sum()), float(max(1, rounds_with_kills))),
            "signal_round_entropy": _normalized_entropy(signal_round_counts),
            "top_signal_round_share": round(top_signal_round_share, 6),
            "weapon_entropy": _normalized_entropy(weapon_counts),
            "dominant_weapon_share": round(dominant_weapon_share, 6),
            "victim_entropy": _normalized_entropy(victim_counts),
            "top_victim_share": round(top_victim_share, 6),
            "kill_density": float(n_kills / max(1, rounds_with_kills)),
            "headshot_rate": _laplace(float(g["headshot"].sum()), float(n_kills)),
            "prefire_rate": _laplace(float(g["is_prefire"].sum()), float(n_kills)),
            "thrusmoke_kill_rate": _laplace(float(g["is_thrusmoke"].sum()), float(n_kills)),
            "micropeek_4_rate": _laplace(float(g["is_micropeek_4"].sum()), float(n_kills)),
            "long_range_kill_share": _laplace(float(long_range_mask.sum()), float(n_kills)),
            "long_range_fast_rt_rate_4": _laplace(float(g["is_long_range_fast_rt_4"].sum()), float(max(1, int(long_range_mask.sum())))),
            "fast_rt_rate": _laplace(float((g["rt_ticks"] <= 8).fillna(False).sum()), float(max(1, rt_n))),
            "rt_median": _safe_float(rt.median(), 0.0),
            "rt_p10": _safe_float(rt.quantile(0.10), 0.0) if rt_n else 0.0,
            "distance_mean": _safe_float(g["distance"].mean(), 0.0),
            "victim_strength_mean": _safe_float(g["victim_demo_kills"].mean(), 0.0),
            "victim_strength_median": _safe_float(g["victim_demo_kills"].median(), 0.0),
            "victim_strength_low_share": _laplace(float((g["victim_demo_kills"] <= g["victim_demo_kills"].median()).sum()), float(n_kills)),
        }
        rows.append(row)

    return pd.DataFrame(rows)


def _encounter_summary(enc: pd.DataFrame) -> pd.DataFrame:
    if enc.empty:
        return pd.DataFrame()

    work = enc.copy()
    work["attacker_steamid"] = work["attacker_steamid"].astype(str).str.strip()
    for col in [
        "visible_ratio",
        "time_to_first_shot",
        "time_to_first_damage",
        "aim_error_at_first_visible",
        "aim_error_min",
        "aim_acquire_time",
        "aim_error_collapse_rate",
        "aim_error_collapse_ratio",
        "post_acquire_error_std",
        "pre_shot_aim_error_mean",
        "pre_shot_aim_error_std",
        "acquire_to_shot_lag",
        "snap_velocity_early_max",
        "snap_velocity_to_shot_max",
        "snap_jerk_early_max",
        "snap_jerk_to_shot_max",
        "distance_mean",
        "shot_rate_per_128",
        "damage_count",
    ]:
        if col in work.columns:
            work[col] = pd.to_numeric(work[col], errors="coerce")
    for col in ["shot_before_aim_acquire", "ended_in_kill_within_y", "ended_in_damage"]:
        if col in work.columns:
            work[col] = work[col].fillna(False).astype(bool)

    rows: list[dict[str, object]] = []
    for (demo_id, steamid), g in work.groupby(["demo_id", "attacker_steamid"], sort=False):
        enc_n = int(len(g))
        visible_ratio = pd.to_numeric(g.get("visible_ratio"), errors="coerce").dropna()
        aim_err_min = pd.to_numeric(g.get("aim_error_min"), errors="coerce").dropna()
        aim_acq = pd.to_numeric(g.get("aim_acquire_time"), errors="coerce").dropna()
        collapse_rate = pd.to_numeric(_series_or_default(g, "aim_error_collapse_rate", np.nan), errors="coerce")
        collapse_ratio = pd.to_numeric(_series_or_default(g, "aim_error_collapse_ratio", np.nan), errors="coerce")
        post_lock_std = pd.to_numeric(_series_or_default(g, "post_acquire_error_std", np.nan), errors="coerce")
        pre_shot_err = pd.to_numeric(_series_or_default(g, "pre_shot_aim_error_mean", np.nan), errors="coerce")
        pre_shot_err_std = pd.to_numeric(_series_or_default(g, "pre_shot_aim_error_std", np.nan), errors="coerce")
        acquire_shot_lag = pd.to_numeric(_series_or_default(g, "acquire_to_shot_lag", np.nan), errors="coerce")
        snap_vel = pd.to_numeric(_series_or_default(g, "snap_velocity_early_max", np.nan), errors="coerce")
        snap_vel_shot = pd.to_numeric(_series_or_default(g, "snap_velocity_to_shot_max", np.nan), errors="coerce")
        snap_jerk = pd.to_numeric(_series_or_default(g, "snap_jerk_early_max", np.nan), errors="coerce")
        snap_jerk_shot = pd.to_numeric(_series_or_default(g, "snap_jerk_to_shot_max", np.nan), errors="coerce")
        distance_mean = pd.to_numeric(_series_or_default(g, "distance_mean", np.nan), errors="coerce").fillna(0.0)
        rel_speed = pd.to_numeric(_series_or_default(g, "relative_speed_mean", np.nan), errors="coerce").fillna(0.0)
        att_speed = pd.to_numeric(_series_or_default(g, "attacker_speed_mean", np.nan), errors="coerce").fillna(0.0)
        vic_speed = pd.to_numeric(_series_or_default(g, "victim_speed_mean", np.nan), errors="coerce").fillna(0.0)
        hard_mask = (distance_mean >= 900.0) | (rel_speed >= 6.0) | (att_speed >= 4.0) | (vic_speed >= 4.0) | ((pd.to_numeric(g.get("visible_ratio"), errors="coerce") <= 0.75).fillna(False))
        easy_mask = ~hard_mask
        rows.append({
            "demo_id": str(demo_id),
            "attacker_steamid": str(steamid),
            "enc_n": enc_n,
            "low_visibility_encounter_rate": _laplace(float((pd.to_numeric(g.get("visible_ratio"), errors="coerce") <= 0.65).fillna(False).sum()), float(enc_n)),
            "low_visibility_kill_end_rate": _laplace(float(((pd.to_numeric(g.get("visible_ratio"), errors="coerce") <= 0.65).fillna(False) & g.get("ended_in_kill_within_y", pd.Series(False, index=g.index)).fillna(False).astype(bool)).sum()), float(max(1, (pd.to_numeric(g.get("visible_ratio"), errors="coerce") <= 0.65).fillna(False).sum()))),
            "shot_before_acquire_rate": _laplace(float(g.get("shot_before_aim_acquire", pd.Series(False, index=g.index)).fillna(False).astype(bool).sum()), float(enc_n)),
            "enc_kill_end_rate": _laplace(float(g.get("ended_in_kill_within_y", pd.Series(False, index=g.index)).fillna(False).astype(bool).sum()), float(enc_n)),
            "visible_ratio_median": _safe_float(visible_ratio.median(), 0.0),
            "aim_error_min_median": _safe_float(aim_err_min.median(), 0.0),
            "aim_acquire_time_median": _safe_float(aim_acq.median(), 0.0),
            "aim_error_collapse_rate_high": _laplace(float((collapse_rate >= 0.5).fillna(False).sum()), float(enc_n)),
            "aim_error_collapse_ratio_high": _laplace(float((collapse_ratio >= 3.0).fillna(False).sum()), float(enc_n)),
            "post_acquire_error_std_low": _laplace(float((post_lock_std <= 0.35).fillna(False).sum()), float(enc_n)),
            "pre_shot_error_low": _laplace(float((pre_shot_err <= 1.25).fillna(False).sum()), float(enc_n)),
            "pre_shot_error_std_low": _laplace(float((pre_shot_err_std <= 0.35).fillna(False).sum()), float(enc_n)),
            "acquire_to_shot_lag_low": _laplace(float((acquire_shot_lag <= 2.0).fillna(False).sum()), float(enc_n)),
            "snap_velocity_high": _laplace(float(((snap_vel >= 4.0) | (snap_vel_shot >= 4.0)).fillna(False).sum()), float(enc_n)),
            "snap_jerk_high": _laplace(float(((snap_jerk >= 1.5) | (snap_jerk_shot >= 1.5)).fillna(False).sum()), float(enc_n)),
            "hard_encounter_rate": _laplace(float(hard_mask.sum()), float(enc_n)),
            "hard_low_error_rate": _laplace(float((hard_mask & (aim_err_min <= 0.9)).sum()), float(max(1, int(hard_mask.sum())))),
            "hard_fast_acquire_rate": _laplace(float((hard_mask & (aim_acq <= 4.0)).sum()), float(max(1, int(hard_mask.sum())))),
            "hard_clean_preshot_rate": _laplace(float((hard_mask & (pre_shot_err <= 1.25)).sum()), float(max(1, int(hard_mask.sum())))),
            "hard_low_noise_rate": _laplace(float((hard_mask & (post_lock_std <= 0.35)).sum()), float(max(1, int(hard_mask.sum())))),
            "hard_finish_rate": _laplace(float((hard_mask & _series_or_default(g, "ended_in_kill_within_y", False).fillna(False).astype(bool)).sum()), float(max(1, int(hard_mask.sum())))),
            "easy_low_error_rate": _laplace(float((easy_mask & (aim_err_min <= 0.9)).sum()), float(max(1, int(easy_mask.sum())))),
            "encounter_distance_mean": _safe_float(pd.to_numeric(g.get("distance_mean"), errors="coerce").mean(), 0.0),
        })
    return pd.DataFrame(rows)


def build_demo_player_summary(eng: pd.DataFrame, enc: pd.DataFrame | None = None) -> pd.DataFrame:
    kill_summary = _kill_summary(eng)
    enc_summary = _encounter_summary(enc if enc is not None else pd.DataFrame())
    if kill_summary.empty:
        return kill_summary
    summary = kill_summary.merge(enc_summary, on=["demo_id", "attacker_steamid"], how="left") if not enc_summary.empty else kill_summary.copy()

    demo_total_kills = summary.groupby("demo_id")["n_kills"].transform("sum").replace(0, np.nan)
    summary["kill_share"] = summary["n_kills"] / demo_total_kills
    summary["victim_strength_mean_pct"] = summary.groupby("demo_id")["victim_strength_mean"].transform(lambda s: _percentile_series(s, ascending=True))
    summary["n_kills_pct"] = summary.groupby("demo_id")["n_kills"].transform(lambda s: _percentile_series(s, ascending=True))
    summary["kill_density_pct"] = summary.groupby("demo_id")["kill_density"].transform(lambda s: _percentile_series(s, ascending=True))
    summary["headshot_pct"] = summary.groupby("demo_id")["headshot_rate"].transform(lambda s: _percentile_series(s, ascending=True))
    summary["prefire_pct"] = summary.groupby("demo_id")["prefire_rate"].transform(lambda s: _percentile_series(s, ascending=True))
    summary["thrusmoke_pct"] = summary.groupby("demo_id")["thrusmoke_kill_rate"].transform(lambda s: _percentile_series(s, ascending=True))
    summary["micropeek_pct"] = summary.groupby("demo_id")["micropeek_4_rate"].transform(lambda s: _percentile_series(s, ascending=True))
    summary["fast_rt_pct"] = summary.groupby("demo_id")["fast_rt_rate"].transform(lambda s: _percentile_series(s, ascending=True))
    summary["long_fast_rt_pct"] = summary.groupby("demo_id")["long_range_fast_rt_rate_4"].transform(lambda s: _percentile_series(s, ascending=True))
    summary["rt_median_pct"] = summary.groupby("demo_id")["rt_median"].transform(lambda s: _percentile_series(s, ascending=False))
    summary["round_concentration_pct"] = summary.groupby("demo_id")["top_round_kill_share"].transform(lambda s: _percentile_series(s, ascending=True))
    summary["signal_concentration_pct"] = summary.groupby("demo_id")["top_signal_round_share"].transform(lambda s: _percentile_series(s, ascending=True))
    summary["weapon_specialization_pct"] = summary.groupby("demo_id")["dominant_weapon_share"].transform(lambda s: _percentile_series(s, ascending=True))
    summary["round_spread_pct"] = summary.groupby("demo_id")["round_kill_entropy"].transform(lambda s: _percentile_series(s, ascending=True))
    summary["weapon_spread_pct"] = summary.groupby("demo_id")["weapon_entropy"].transform(lambda s: _percentile_series(s, ascending=True))

    if "low_visibility_encounter_rate" in summary.columns:
        summary["low_visibility_pct"] = summary.groupby("demo_id")["low_visibility_encounter_rate"].transform(lambda s: _percentile_series(s, ascending=True))
        summary["shot_before_acquire_pct"] = summary.groupby("demo_id")["shot_before_acquire_rate"].transform(lambda s: _percentile_series(s, ascending=True))
        summary["aim_error_min_pct"] = summary.groupby("demo_id")["aim_error_min_median"].transform(lambda s: _percentile_series(s, ascending=False))
        summary["aim_acquire_pct"] = summary.groupby("demo_id")["aim_acquire_time_median"].transform(lambda s: _percentile_series(s, ascending=False))
        summary["aim_process_global_raw"] = summary.apply(
            lambda row: _clamp01(
                _mean_non_null(
                    row.get("aim_error_collapse_rate_high"),
                    row.get("aim_error_collapse_ratio_high"),
                    row.get("pre_shot_error_low"),
                    row.get("pre_shot_error_std_low"),
                    row.get("post_acquire_error_std_low"),
                    row.get("acquire_to_shot_lag_low"),
                    row.get("snap_velocity_high"),
                    row.get("snap_jerk_high"),
                    row.get("hard_low_error_rate"),
                    row.get("hard_fast_acquire_rate"),
                    row.get("hard_clean_preshot_rate"),
                    row.get("hard_low_noise_rate"),
                )
            ),
            axis=1,
        )
        summary["aim_process_global_pct"] = summary.groupby("demo_id")["aim_process_global_raw"].transform(lambda s: _percentile_series(s, ascending=True))
        summary["aim_process_global_range"] = summary.groupby("demo_id")["aim_process_global_raw"].transform(
            lambda s: float(s.max() - s.min()) if s.notna().any() else 0.0
        )
        summary["difficulty_precision_raw"] = summary.apply(
            lambda row: _clamp01(
                _mean_non_null(
                    row.get("hard_low_error_rate"),
                    row.get("hard_fast_acquire_rate"),
                    row.get("hard_clean_preshot_rate"),
                    row.get("hard_low_noise_rate"),
                    row.get("hard_finish_rate"),
                    row.get("hard_encounter_rate"),
                )
            ),
            axis=1,
        )
        summary["difficulty_precision_pct"] = summary.groupby("demo_id")["difficulty_precision_raw"].transform(lambda s: _percentile_series(s, ascending=True))
        summary["difficulty_precision_range"] = summary.groupby("demo_id")["difficulty_precision_raw"].transform(
            lambda s: float(s.max() - s.min()) if s.notna().any() else 0.0
        )
    else:
        summary["low_visibility_pct"] = np.nan
        summary["shot_before_acquire_pct"] = np.nan
        summary["aim_error_min_pct"] = np.nan
        summary["aim_acquire_pct"] = np.nan
        summary["aim_process_global_raw"] = np.nan
        summary["aim_process_global_pct"] = np.nan
        summary["difficulty_precision_raw"] = np.nan
        summary["difficulty_precision_pct"] = np.nan
        summary["aim_process_global_range"] = 0.0
        summary["difficulty_precision_range"] = 0.0

    summary["low_vis_precision_retention"] = summary.apply(
        lambda row: min(1.5, max(0.0, _safe_ratio(row.get("low_visibility_kill_end_rate"), row.get("enc_kill_end_rate"), 0.0))),
        axis=1,
    )
    summary["timing_selectivity"] = summary.apply(
        lambda row: _clamp01(
            max(
                _safe_float(row.get("top_signal_round_share"), 0.0),
                _safe_float(row.get("dominant_weapon_share"), 0.0),
                _safe_float(row.get("top_round_kill_share"), 0.0),
            )
        ),
        axis=1,
    )
    summary["process_contradiction_score"] = summary.apply(
        lambda row: _clamp01(
            _mean_non_null(
                row.get("shot_before_acquire_rate"),
                row.get("low_visibility_kill_end_rate"),
                row.get("low_vis_precision_retention"),
                row.get("fast_rt_rate"),
                row.get("thrusmoke_kill_rate"),
                row.get("aim_process_global_raw"),
                row.get("difficulty_precision_raw"),
            )
        ),
        axis=1,
    )
    summary["process_contradiction_pct"] = summary.groupby("demo_id")["process_contradiction_score"].transform(lambda s: _percentile_series(s, ascending=True))
    summary["process_contradiction_range"] = summary.groupby("demo_id")["process_contradiction_score"].transform(
        lambda s: float(s.max() - s.min()) if s.notna().any() else 0.0
    )
    summary["low_vis_precision_pct"] = summary.groupby("demo_id")["low_vis_precision_retention"].transform(lambda s: _percentile_series(s, ascending=True))
    summary["timing_selectivity_pct"] = summary.groupby("demo_id")["timing_selectivity"].transform(lambda s: _percentile_series(s, ascending=True))

    summary = summary.replace([np.inf, -np.inf], np.nan)
    return summary


def _mean_non_null(*values: float | None) -> float:
    vals = [float(v) for v in values if v is not None and not pd.isna(v)]
    return float(sum(vals) / len(vals)) if vals else 0.0


def _safe_ratio(numerator: float | int | None, denominator: float | int | None, default: float = 0.0) -> float:
    num = _safe_float(numerator, None)
    den = _safe_float(denominator, None)
    if num is None or den is None or den <= 0:
        return default
    return float(num / den)


def _display_count(value: float | int | None) -> str:
    if value is None or pd.isna(value):
        return "--"
    return str(int(round(float(value))))


def _display_pct(value: float | int | None) -> str:
    if value is None or pd.isna(value):
        return "--"
    return f"{_clamp01(value) * 100:.1f}%"


def _derive_archetype(
    mechanics: float,
    timing: float,
    occlusion: float,
    stability: float,
    context_fit: float,
    sample_limit: float,
    contradiction_override: float = 0.0,
    model_support: float = 0.0,
    absolute_process_evidence: float = 0.0,
    compressed_lobby: bool = False,
) -> tuple[str, str]:
    strong_process_support = max(model_support, absolute_process_evidence) >= 0.46
    moderate_process_support = max(model_support, absolute_process_evidence) >= 0.34
    if contradiction_override >= 0.72 and strong_process_support:
        return "Process-breaking outlier", "The player's process-level behavior stays unusually clean in contexts where human play normally degrades."
    if contradiction_override >= 0.62 and stability >= 0.56 and strong_process_support:
        return "Low-degradation mechanical anomaly", "Mechanical output remains unusually stable across varied engagements instead of decaying like a human baseline."
    if sample_limit >= 0.7 and stability < 0.5:
        return "Thin-evidence anomaly", "The player stands out, but the evidence is narrow enough that the profile remains fragile."
    if occlusion >= max(mechanics, timing) and occlusion >= 0.54:
        return "Occlusion-heavy outlier", "The separation comes disproportionately from low-visibility or compromised-sightline fights."
    if timing >= max(mechanics, occlusion) and context_fit >= 0.72 and contradiction_override < 0.38:
        return "Mechanical standout, context-consistent", "The player is strong across the lobby, and the current match context explains a material share of the separation."
    if timing >= max(mechanics, occlusion):
        return "Info-leaning anomaly", "The standout shape is driven more by timing and sequence control than by raw mechanical output."
    if mechanics >= 0.58 and stability >= 0.56 and context_fit >= 0.72 and contradiction_override < 0.4 and moderate_process_support:
        return "Stable standout", "The profile is broad enough that simple hot-round explanations are less convincing."
    if mechanics >= 0.54 and stability < 0.5:
        return "High-variance carry", "Mechanical output is elevated, but the match story is concentrated rather than broad."
    return "Mixed anomaly", "No single component dominates the case, so the profile should be read as a mixed deviation."


def interpretation_from_summary(summary_row: pd.Series | dict, *, risk: float | None = None, confidence: float | None = None, ci_low: float | None = None, ci_high: float | None = None, rank: int | None = None, total_players: int | None = None) -> dict:
    row = summary_row if isinstance(summary_row, dict) else summary_row.to_dict()
    risk = _clamp01(risk if risk is not None else row.get("risk"))
    confidence = _clamp01(confidence if confidence is not None else row.get("confidence"))
    ci_low = _safe_float(ci_low if ci_low is not None else row.get("ci_low"), None)
    ci_high = _safe_float(ci_high if ci_high is not None else row.get("ci_high"), None)
    ci_width = max(0.0, (ci_high - ci_low)) if ci_low is not None and ci_high is not None else max(0.0, 0.28 - confidence * 0.18)

    mechanics = _mean_non_null(row.get("headshot_pct"), row.get("long_fast_rt_pct"), row.get("aim_error_min_pct"), row.get("aim_acquire_pct"))
    timing = _mean_non_null(row.get("prefire_pct"), row.get("fast_rt_pct"), row.get("micropeek_pct"), row.get("shot_before_acquire_pct"), row.get("rt_median_pct"))
    occlusion = _mean_non_null(row.get("thrusmoke_pct"), row.get("low_visibility_pct"))
    decision = _mean_non_null(row.get("kill_density_pct"), 1.0 - _safe_float(row.get("top_victim_share"), 0.0), row.get("weapon_spread_pct"))
    global_process_anomaly = _clamp01(_safe_float(row.get("aim_process_global_raw"), _safe_float(row.get("aim_process_global_score"), 0.0)))
    global_process_percentile = _clamp01(_safe_float(row.get("aim_process_global_pct"), global_process_anomaly))
    difficulty_precision = _clamp01(_safe_float(row.get("difficulty_precision_raw"), 0.0))
    difficulty_precision_pct = _clamp01(_safe_float(row.get("difficulty_precision_pct"), difficulty_precision))
    process_contradiction_raw = _clamp01(_safe_float(row.get("process_contradiction_score"), 0.0))
    process_range = _clamp01(_safe_float(row.get("process_contradiction_range"), 0.0) / 0.18)
    global_range = _clamp01(_safe_float(row.get("aim_process_global_range"), 0.0) / 0.12)
    difficulty_range = _clamp01(_safe_float(row.get("difficulty_precision_range"), 0.0) / 0.28)
    separation_strength = _mean_non_null(process_range, global_range, difficulty_range)
    compressed_lobby = separation_strength < 0.55
    global_process_percentile = 0.5 + ((global_process_percentile - 0.5) * (0.35 + (0.65 * separation_strength)))
    difficulty_precision_pct = 0.5 + ((difficulty_precision_pct - 0.5) * (0.35 + (0.65 * separation_strength)))
    process_contradiction_pct = _clamp01(_safe_float(row.get("process_contradiction_pct"), process_contradiction_raw))
    process_contradiction_pct = 0.5 + ((process_contradiction_pct - 0.5) * (0.35 + (0.65 * separation_strength)))
    contradiction = _mean_non_null(process_contradiction_pct, row.get("low_vis_precision_pct"), row.get("shot_before_acquire_pct"), global_process_percentile, difficulty_precision_pct)
    selective_activation = _mean_non_null(row.get("timing_selectivity_pct"), row.get("round_concentration_pct"), row.get("weapon_specialization_pct"))
    absolute_process_evidence = _clamp01(_mean_non_null(global_process_anomaly, difficulty_precision, process_contradiction_raw))
    model_support = _clamp01(max(risk, absolute_process_evidence))

    round_breadth = _clamp01((_safe_float(row.get("round_kill_entropy"), 0.0) * 0.7) + ((1.0 - _safe_float(row.get("top_round_kill_share"), 0.0)) * 0.3))
    weapon_breadth = _clamp01((_safe_float(row.get("weapon_entropy"), 0.0) * 0.7) + ((1.0 - _safe_float(row.get("dominant_weapon_share"), 0.0)) * 0.3))
    visibility_breadth = _clamp01(1.0 - max(0.0, occlusion - 0.5) * 0.9)
    engagement_breadth = _clamp01(1.0 - max(0.0, _safe_float(row.get("top_signal_round_share"), 0.0) - 0.33) * 1.1)
    stability = _clamp01((_mean_non_null(round_breadth, weapon_breadth, visibility_breadth, engagement_breadth) * 0.72) + (confidence * 0.28))

    sample_limit = _clamp01(max(0.0, (1.0 - min(_safe_float(row.get("rt_n"), 0.0), 18.0) / 18.0) * 0.55 + (1.0 - min(_safe_float(row.get("n_kills"), 0.0), 16.0) / 16.0) * 0.25 + ci_width * 0.6))
    weak_opponent = _clamp01(1.0 - _safe_float(row.get("victim_strength_mean_pct"), 0.5))
    skill_gap = _clamp01(_mean_non_null(row.get("n_kills_pct"), row.get("kill_density_pct"), row.get("round_spread_pct"), row.get("victim_strength_mean_pct")))
    weapon_mix = _clamp01(_safe_float(row.get("dominant_weapon_share"), 0.0))
    engagement_mix = _clamp01(_mean_non_null(row.get("long_range_kill_share"), row.get("thrusmoke_kill_rate"), row.get("top_signal_round_share")))
    map_round_context = _clamp01(_safe_float(row.get("top_round_kill_share"), 0.0))

    explanation_pressure = (skill_gap * 0.16) + (weak_opponent * 0.14) + (sample_limit * 0.18) + (weapon_mix * 0.08) + (engagement_mix * 0.08) + (map_round_context * 0.06)
    contradiction_override = _clamp01((contradiction * 0.5) + (global_process_percentile * 0.18) + (difficulty_precision_pct * 0.2) + (timing * 0.08) + (occlusion * 0.02) + (mechanics * 0.01) + (stability * 0.01))
    if compressed_lobby and model_support < 0.32:
        contradiction_override *= 0.78
    blatant_override = (
        (contradiction_override >= 0.72 and max(model_support, absolute_process_evidence) >= 0.46)
        or (difficulty_precision_pct >= 0.9 and difficulty_precision >= 0.5 and max(model_support, absolute_process_evidence) >= 0.48)
        or (contradiction_override >= 0.66 and timing >= 0.68 and max(model_support, absolute_process_evidence) >= 0.46)
        or (contradiction_override >= 0.62 and occlusion >= 0.72 and max(model_support, absolute_process_evidence) >= 0.46)
    )
    context_fit = _clamp01(1.0 - explanation_pressure - (contradiction_override * 1.08) + (stability * 0.02))
    if blatant_override:
        context_fit = min(context_fit, 0.14)
    behavioral_deviation = _clamp01(max(risk, _mean_non_null(mechanics, timing, occlusion, decision, contradiction) * 0.64 + max(mechanics, timing, occlusion, contradiction) * 0.36))
    review_priority = _clamp01((behavioral_deviation * 0.28) + ((1.0 - context_fit) * 0.26) + (contradiction_override * 0.28) + (stability * 0.08) + ((1.0 - sample_limit) * 0.04) + (selective_activation * 0.06))
    if compressed_lobby and risk < 0.1 and absolute_process_evidence < 0.34 and not blatant_override:
        review_priority = min(review_priority, 0.68 + (absolute_process_evidence * 0.18))
        context_fit = max(context_fit, 0.24)
    if not blatant_override and max(risk, absolute_process_evidence) < 0.46:
        support_gate = _clamp01((max(risk, absolute_process_evidence) - 0.18) / 0.28)
        review_priority = min(review_priority, 0.54 + (support_gate * 0.18) + (stability * 0.06))
        context_fit = max(context_fit, 0.26 + ((1.0 - support_gate) * 0.16))
    if blatant_override:
        review_priority = max(review_priority, 0.92)

    archetype_label, archetype_summary = _derive_archetype(
        mechanics,
        timing,
        occlusion,
        stability,
        context_fit,
        sample_limit,
        contradiction_override,
        model_support=model_support,
        absolute_process_evidence=absolute_process_evidence,
        compressed_lobby=compressed_lobby,
    )
    components = [
        {"key": "mechanics", "label": "Mechanics", "share": max(0.05, mechanics), "summary": "Driven by mechanical conversion, aim acquisition, and finishing quality."},
        {"key": "information_timing", "label": "Information / timing", "share": max(0.05, timing), "summary": "Driven by prefire, micropeek, and fast timing patterns."},
        {"key": "occlusion", "label": "Occlusion", "share": max(0.05, occlusion), "summary": "Driven by low-visibility and smoke-adjacent engagements."},
        {"key": "decision_discipline", "label": "Decision discipline", "share": max(0.05, decision), "summary": "Driven by engagement shaping, victim spread, and general kill structure."},
        {"key": "concentration", "label": "Stability / concentration", "share": max(0.05, 1.0 - stability), "summary": "Captures whether the signal is broad or concentrated."},
    ]
    total = sum(item["share"] for item in components) or 1.0
    for item in components:
        item["share"] = round(item["share"] / total, 4)

    remaining_signal = "yes" if blatant_override or context_fit <= 0.42 else "mixed" if context_fit <= 0.62 else "uncertain"
    if blatant_override:
        review_title = "Review target acquisition and pre-visibility alignment"
    elif contradiction_override >= 0.58:
        review_title = "Review pre-acquire shots and snap corrections"
    elif occlusion >= max(mechanics, timing):
        review_title = "Compare POV in low-visibility engagements"
    elif timing >= mechanics:
        review_title = "Review timing around first-contact fights"
    else:
        review_title = "Compare standout rounds against stronger opponents"
    lobby_percentile = _clamp01(1.0 - ((rank - 1) / max(1, total_players - 1))) if rank is not None and total_players and total_players > 1 else 1.0
    match_profile_summary = (
        f"Ranked #{rank} of {total_players} in this lobby. The standout shape comes from actual per-match event structure rather than a generic leaderboard score."
        if rank is not None and total_players
        else "Derived from actual per-match event structure and compared only against this lobby."
    )
    evidence_basis_summary = (
        f"Built from {_display_count(row.get('n_kills'))} kills, {_display_count(row.get('rt_n'))} RT-supported kills, and {_display_count(row.get('enc_n'))} encounters in this match."
    )
    match_profile_stats = [
        {"key": "rank", "label": "Lobby standing", "display_value": (f"#{rank}/{total_players}" if rank is not None and total_players else "--"), "value": (None if rank is None or not total_players else float(rank) / float(total_players)), "summary": "This is a match-relative position, not a global claim."},
        {"key": "lobby_percentile", "label": "Lobby percentile", "display_value": _display_pct(lobby_percentile), "value": round(lobby_percentile, 4), "summary": "Higher means the player sits closer to the top of this match-relative ranking."},
        {"key": "kills", "label": "Kills in sample", "display_value": _display_count(row.get("n_kills")), "value": _safe_float(row.get("n_kills"), None), "summary": "The number of labeled kill rows available for this player in the current match."},
        {"key": "encounters", "label": "Encounters in sample", "display_value": _display_count(row.get("enc_n")), "value": _safe_float(row.get("enc_n"), None), "summary": "Broader encounter volume used to pressure-test selectivity and visibility-driven behavior."},
        {"key": "rounds", "label": "Rounds with kills", "display_value": _display_count(row.get("rounds_with_kills")), "value": _safe_float(row.get("rounds_with_kills"), None), "summary": "How many rounds actually contribute to the player’s kill-based profile."},
        {"key": "rt_support", "label": "RT-supported kills", "display_value": _display_count(row.get("rt_n")), "value": _safe_float(row.get("rt_n"), None), "summary": "Kill events with usable visibility-to-shot timing support."},
    ]
    relative_markers = [
        {"key": "prefire_pct", "label": "Prefire percentile", "display_value": _display_pct(row.get("prefire_pct")), "value": round(_clamp01(row.get("prefire_pct")), 4), "summary": "How extreme the player's prefire rate is relative to the current lobby."},
        {"key": "rt_median_pct", "label": "Timing percentile", "display_value": _display_pct(row.get("rt_median_pct")), "value": round(_clamp01(row.get("rt_median_pct")), 4), "summary": "Where the player's median visibility-to-shot timing sits inside this match."},
        {"key": "thrusmoke_pct", "label": "Occlusion percentile", "display_value": _display_pct(row.get("thrusmoke_pct")), "value": round(_clamp01(row.get("thrusmoke_pct")), 4), "summary": "How strongly smoke or low-visibility outcomes separate from the lobby."},
        {"key": "headshot_pct", "label": "Mechanical percentile", "display_value": _display_pct(row.get("headshot_pct")), "value": round(_clamp01(row.get("headshot_pct")), 4), "summary": "A match-relative proxy for mechanical conversion."},
        {"key": "process_contradiction_pct", "label": "Process contradiction", "display_value": _display_pct(row.get("process_contradiction_pct")), "value": round(_clamp01(row.get("process_contradiction_pct")), 4), "summary": "How strongly the encounter process departs from ordinary human degradation in this lobby."},
        {"key": "aim_process_global_pct", "label": "Global aim-process anomaly", "display_value": _display_pct(global_process_percentile), "value": round(global_process_percentile, 4), "summary": "How strongly the player's aim-process shape departs from ordinary encounter behavior, beyond this single lobby ordering."},
        {"key": "difficulty_precision_pct", "label": "Precision under difficulty", "display_value": _display_pct(difficulty_precision_pct), "value": round(difficulty_precision_pct, 4), "summary": "How often the player's aim remains unusually clean in harder fights with distance, speed, or lower visibility pressure."},
        {"key": "round_concentration_pct", "label": "Round concentration", "display_value": _display_pct(row.get("round_concentration_pct")), "value": round(_clamp01(row.get("round_concentration_pct")), 4), "summary": "Higher means the standout shape is clustered in fewer rounds."},
        {"key": "weapon_specialization_pct", "label": "Weapon specialization", "display_value": _display_pct(row.get("weapon_specialization_pct")), "value": round(_clamp01(row.get("weapon_specialization_pct")), 4), "summary": "Higher means the shape is more concentrated in a narrower weapon mix."},
    ]

    return {
        "archetype": {"label": archetype_label, "summary": archetype_summary},
        "behavior_profile": {
            "headline": "Process-level contradictions persist across the match and are not adequately explained by ordinary performance context." if blatant_override else "Broad process abnormalities persist across the match, including pre-acquire and low-visibility conversion patterns." if contradiction_override >= 0.58 else "Stands out mostly through timing and low-visibility sequencing, not pure mechanics." if timing >= max(mechanics, occlusion) else "High mechanical separation, but the review should focus on whether the process degrades like a human under pressure." if mechanics >= max(timing, occlusion) else "Narrow anomaly concentrated in a specific fight shape rather than broad dominance.",
            "summary": archetype_summary if contradiction_override < 0.58 and not blatant_override else "The standout is not just strong output. The encounter process itself remains unusually clean in contexts where human play should degrade.",
        },
        "match_profile": {
            "summary": match_profile_summary,
            "stats": match_profile_stats,
            "relative_markers": relative_markers,
        },
        "evidence_basis": {
            "summary": evidence_basis_summary,
            "stats": [
                {"key": "kills", "label": "Kill rows", "display_value": _display_count(row.get("n_kills")), "value": _safe_float(row.get("n_kills"), None), "summary": "Kill rows carried into the player-demo aggregate."},
                {"key": "rt_n", "label": "RT-supported kills", "display_value": _display_count(row.get("rt_n")), "value": _safe_float(row.get("rt_n"), None), "summary": "Events with usable timing support."},
                {"key": "enc_n", "label": "Encounter rows", "display_value": _display_count(row.get("enc_n")), "value": _safe_float(row.get("enc_n"), None), "summary": "Encounter-level rows used for context and selectivity checks."},
                {"key": "confidence", "label": "Support level", "display_value": _display_pct(confidence), "value": round(confidence, 4), "summary": "Evidence stability after sample-size and uncertainty effects."},
            ],
        },
        "behavioral_deviation": round(behavioral_deviation, 4),
        "global_process_anomaly": round(global_process_anomaly, 4),
        "context_fit": round(context_fit, 4),
        "signal_stability": round(stability, 4),
        "review_priority": round(review_priority, 4),
        "support_level": round(confidence, 4),
        "signal_components": components,
        "context_adjustment": {
            "summary": "Ordinary match context does not adequately explain the observed process-level anomaly." if blatant_override or contradiction_override >= 0.58 else "Several ordinary explanations partially account for the standout profile, but material unexplained signal remains." if remaining_signal != "uncertain" else "Ordinary performance and match context explain a large share of the observed deviation.",
            "remaining_signal": remaining_signal,
            "normal_explanations": [
                {"key": "skill_gap", "label": "Skill gap explanation", "status": "limited" if contradiction_override >= 0.44 else "strong" if skill_gap >= 0.78 else "partial" if skill_gap >= 0.58 else "limited", "weight": round(skill_gap, 4), "summary": "Broad strength across rounds can explain some output separation, but not process contradictions."},
                {"key": "opponent_pool", "label": "Weak opponent pool", "status": "high" if weak_opponent >= 0.7 else "partial" if weak_opponent >= 0.48 else "limited", "weight": round(weak_opponent, 4), "summary": "Victim quality inside this match may inflate separation."},
                {"key": "sample_size", "label": "Sample size limitation", "status": "high" if sample_limit >= 0.7 else "partial" if sample_limit >= 0.45 else "limited", "weight": round(sample_limit, 4), "summary": "Low event volume widens uncertainty and makes concentration harder to trust."},
                {"key": "weapon_mix", "label": "Weapon mix", "status": "partial" if weapon_mix >= 0.45 else "limited", "weight": round(weapon_mix, 4), "summary": "A narrow weapon profile can make the anomaly look cleaner than it is."},
                {"key": "engagement_mix", "label": "Engagement mix", "status": "partial" if engagement_mix >= 0.45 else "limited", "weight": round(engagement_mix, 4), "summary": "The signal may be concentrated in only certain fight types or sightlines."},
                {"key": "process_contradiction", "label": "Process contradiction", "status": "high" if contradiction_override >= 0.54 else "partial" if contradiction_override >= 0.38 else "limited", "weight": round(contradiction_override, 4), "summary": "Captures whether the encounter process remains unusually clean where human play normally degrades."},
            ],
        },
        "durability": {
            "summary": "The signal is broad enough to survive simple hot-round explanations." if stability >= 0.56 else "The signal is concentrated, so the right question is where it appears, not just how high it ranks.",
            "metrics": [
                {"key": "rounds", "label": "Across rounds", "value": round(round_breadth, 4), "summary": "Breadth across the match rather than only a few standout rounds."},
                {"key": "halves", "label": "Across halves", "value": None, "summary": "Half split is unavailable until side-tagged encounter aggregation is regenerated."},
                {"key": "weapons", "label": "Across weapons", "value": round(weapon_breadth, 4), "summary": "Higher values mean the signal is less weapon-specific."},
                {"key": "visibility", "label": "Across visibility states", "value": round(visibility_breadth, 4), "summary": "Higher values mean the profile is not isolated to smoke or low-visibility moments."},
                {"key": "engagements", "label": "Across engagement types", "value": round(engagement_breadth, 4), "summary": "Higher values mean the anomaly is not just one selective fight pattern."},
            ],
        },
        "review_lens": {
            "title": review_title,
            "summary": "Use the follow-up review to test whether the standout shape repeats in the contexts that actually drive it.",
            "comparisons": [review_title, "Compare standout rounds against opponent POV", "Check whether the same pattern survives outside the dominant weapon or round cluster"],
        },
        "limitations": [
            {"label": "Match-only sample", "severity": "high", "summary": "This interpretation is bounded to one demo and should not be read as a longitudinal claim."},
            {"label": "Signal concentration", "severity": "medium" if stability < 0.56 else "low", "summary": "Concentration metrics come from actual round, weapon, and signal clustering in this match."},
            {"label": "Half split missing", "severity": "medium", "summary": "Current processed demos do not consistently include side-tagged encounter aggregates yet."},
        ],
        "model_notes": [
            "Interpretation is now derived from actual match event structure, not only from the ranked output row.",
            "Future work: regenerate demos with side-tagged encounters and incorporate opponent-quality priors beyond same-match kill graph.",
        ],
    }


def build_demo_interpretations(ranked_rows: pd.DataFrame, eng: pd.DataFrame, enc: pd.DataFrame | None = None) -> dict[str, dict]:
    summary = build_demo_player_summary(eng, enc)
    if summary.empty or ranked_rows.empty:
        return {}
    ranked = ranked_rows.copy()
    ranked["attacker_steamid"] = ranked["attacker_steamid"].astype(str).str.strip()
    merged = ranked.merge(summary, on=["demo_id", "attacker_steamid"], how="left")
    total_players = int(len(merged))
    out: dict[str, dict] = {}
    for rank_idx, (_, row) in enumerate(merged.iterrows(), start=1):
        sid = str(row.get("attacker_steamid", "")).strip()
        risk = _safe_float(row.get("risk"), _safe_float(row.get("proba_calibrated"), _safe_float(row.get("proba_cheater_infer"), 0.0))) or 0.0
        confidence = _safe_float(row.get("confidence"), 0.0) or 0.0
        ci_low = _safe_float(row.get("ci_low"), None)
        ci_high = _safe_float(row.get("ci_high"), None)
        out[sid] = interpretation_from_summary(row, risk=risk, confidence=confidence, ci_low=ci_low, ci_high=ci_high, rank=rank_idx, total_players=total_players)
    return out

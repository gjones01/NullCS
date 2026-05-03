from __future__ import annotations

from dataclasses import dataclass
import importlib.util
from pathlib import Path
import json
import math
import pickle
import re

import numpy as np
import pandas as pd
import torch
from torch import nn


ENCOUNTER_META_COLUMNS = {
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
    "weapon",
    "label",
    "dataset_source",
}

TEMPORAL_CHANNEL_COLUMNS = [
    "aim_error_deg",
    "aim_error_yaw_abs",
    "aim_error_pitch_abs",
    "aim_error_delta",
    "aim_error_delta_abs",
    "aim_error_accel",
    "mouse_delta_abs",
    "a_mdx",
    "a_mdy",
    "cmd_yaw_delta",
    "cmd_pitch_delta",
    "cmd_view_gap_yaw",
    "cmd_view_gap_pitch",
    "distance",
    "attacker_speed",
    "relative_speed",
    "angular_velocity",
    "angular_jerk",
    "los_angular_velocity",
    "los_angular_jerk",
    "v_spotted",
    "visible_transition_on",
    "visible_transition_off",
    "ticks_since_visible",
    "a_walking",
    "a_airborne",
    "a_scoped",
    "a_flashed",
    "victim_flashed",
    "shot_event",
    "damage_event",
    "ticks_to_next_shot",
    "ticks_since_last_shot",
    "ticks_to_next_damage",
    "ticks_since_last_damage",
]


def _wrap_deg_np(values: np.ndarray) -> np.ndarray:
    arr = np.asarray(values, dtype=np.float32)
    return ((arr + 180.0) % 360.0) - 180.0


def encounter_model_prefix(mode: str) -> str:
    normalized = str(mode or "cs2cd").strip().lower() or "cs2cd"
    return f"encounter_nn_{normalized}"


def encounter_model_artifacts(models_root: Path, mode: str) -> dict[str, Path]:
    stem = encounter_model_prefix(mode)
    return {
        "model": models_root / f"{stem}.pt",
        "features": models_root / f"{stem}_features.json",
        "preproc": models_root / f"{stem}_preproc.pkl",
        "manifest": models_root / f"{stem}_training_manifest.json",
    }


def encounter_report_artifacts(reports_root: Path, mode: str) -> dict[str, Path]:
    stem = encounter_model_prefix(mode)
    return {
        "oof_encounters_parquet": reports_root / f"{stem}_oof_encounters.parquet",
        "oof_encounters_csv": reports_root / f"{stem}_oof_encounters.csv",
        "oof_players_parquet": reports_root / f"{stem}_oof_players.parquet",
        "oof_players_csv": reports_root / f"{stem}_oof_players.csv",
    }


def encounter_player_feature_path(processed_root: Path, mode: str) -> Path:
    return processed_root / f"{encounter_model_prefix(mode)}_player_features.parquet"


def encounter_infer_player_feature_path(processed_root: Path, demo_id: str) -> Path:
    return processed_root / "demos" / str(demo_id) / "encounter_nn_player_features.parquet"


def select_encounter_feature_columns(df: pd.DataFrame) -> list[str]:
    numeric_cols: list[str] = []
    for col in df.columns:
        if col in ENCOUNTER_META_COLUMNS:
            continue
        series = df[col]
        if pd.api.types.is_bool_dtype(series):
            numeric_cols.append(col)
            continue
        if pd.api.types.is_numeric_dtype(series):
            numeric_cols.append(col)
    return sorted(numeric_cols)


@dataclass
class EncounterPreprocessor:
    feature_cols: list[str]
    medians: dict[str, float]
    means: dict[str, float]
    scales: dict[str, float]

    def transform_frame(self, df: pd.DataFrame) -> np.ndarray:
        work = df.copy()
        for col in self.feature_cols:
            if col not in work.columns:
                work[col] = np.nan
            work[col] = pd.to_numeric(work[col], errors="coerce")
            work[col] = work[col].fillna(self.medians.get(col, 0.0))
            mean = self.means.get(col, 0.0)
            scale = self.scales.get(col, 1.0) or 1.0
            work[col] = (work[col] - mean) / scale
        return work[self.feature_cols].to_numpy(dtype=np.float32, copy=False)

    def save(self, path: Path) -> None:
        with path.open("wb") as f:
            pickle.dump(
                {
                    "feature_cols": self.feature_cols,
                    "medians": self.medians,
                    "means": self.means,
                    "scales": self.scales,
                },
                f,
            )

    @classmethod
    def load(cls, path: Path) -> "EncounterPreprocessor":
        with path.open("rb") as f:
            payload = pickle.load(f)
        return cls(
            feature_cols=list(payload["feature_cols"]),
            medians={str(k): float(v) for k, v in payload["medians"].items()},
            means={str(k): float(v) for k, v in payload["means"].items()},
            scales={str(k): float(v) for k, v in payload["scales"].items()},
        )


@dataclass
class TemporalSequencePreprocessor:
    channel_cols: list[str]
    medians: dict[str, float]
    means: dict[str, float]
    scales: dict[str, float]
    seq_len: int

    def transform_array(self, x: np.ndarray) -> np.ndarray:
        out = np.asarray(x, dtype=np.float32).copy()
        for idx, col in enumerate(self.channel_cols):
            chan = out[:, idx, :]
            chan = np.where(np.isfinite(chan), chan, self.medians.get(col, 0.0))
            chan = (chan - self.means.get(col, 0.0)) / max(self.scales.get(col, 1.0), 1e-6)
            out[:, idx, :] = chan
        return out.astype(np.float32, copy=False)

    def save(self, path: Path) -> None:
        with path.open("wb") as f:
            pickle.dump(
                {
                    "channel_cols": self.channel_cols,
                    "medians": self.medians,
                    "means": self.means,
                    "scales": self.scales,
                    "seq_len": self.seq_len,
                },
                f,
            )

    @classmethod
    def load(cls, path: Path) -> "TemporalSequencePreprocessor":
        with path.open("rb") as f:
            payload = pickle.load(f)
        return cls(
            channel_cols=list(payload["channel_cols"]),
            medians={str(k): float(v) for k, v in payload["medians"].items()},
            means={str(k): float(v) for k, v in payload["means"].items()},
            scales={str(k): float(v) for k, v in payload["scales"].items()},
            seq_len=int(payload["seq_len"]),
        )


def fit_preprocessor(df: pd.DataFrame, feature_cols: list[str]) -> EncounterPreprocessor:
    medians: dict[str, float] = {}
    means: dict[str, float] = {}
    scales: dict[str, float] = {}
    for col in feature_cols:
        series = pd.to_numeric(df[col], errors="coerce") if col in df.columns else pd.Series(dtype=float)
        median = float(series.median()) if series.notna().any() else 0.0
        filled = series.fillna(median)
        mean = float(filled.mean()) if len(filled) else 0.0
        std = float(filled.std(ddof=0)) if len(filled) else 1.0
        medians[col] = median
        means[col] = mean
        scales[col] = std if std > 1e-6 else 1.0
    return EncounterPreprocessor(feature_cols=feature_cols, medians=medians, means=means, scales=scales)


def fit_temporal_preprocessor(x: np.ndarray, channel_cols: list[str], seq_len: int) -> TemporalSequencePreprocessor:
    medians: dict[str, float] = {}
    means: dict[str, float] = {}
    scales: dict[str, float] = {}
    work = np.asarray(x, dtype=np.float32)
    for idx, col in enumerate(channel_cols):
        chan = work[:, idx, :].reshape(-1)
        valid = chan[np.isfinite(chan)]
        median = float(np.median(valid)) if valid.size else 0.0
        filled = np.where(np.isfinite(chan), chan, median)
        mean = float(np.mean(filled)) if filled.size else 0.0
        std = float(np.std(filled)) if filled.size else 1.0
        medians[col] = median
        means[col] = mean
        scales[col] = std if std > 1e-6 else 1.0
    return TemporalSequencePreprocessor(channel_cols=channel_cols, medians=medians, means=means, scales=scales, seq_len=seq_len)


class EncounterMLP(nn.Module):
    def __init__(self, input_dim: int, hidden_dims: tuple[int, ...] = (256, 128, 64), dropout: float = 0.15):
        super().__init__()
        dims = (input_dim, *hidden_dims)
        layers: list[nn.Module] = []
        for i in range(len(dims) - 1):
            in_dim = dims[i]
            out_dim = dims[i + 1]
            layers.extend(
                [
                    nn.Linear(in_dim, out_dim),
                    nn.BatchNorm1d(out_dim),
                    nn.GELU(),
                    nn.Dropout(dropout),
                ]
            )
        layers.append(nn.Linear(dims[-1], 1))
        self.net = nn.Sequential(*layers)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x).squeeze(-1)


class TemporalEncounterCNN(nn.Module):
    def __init__(self, input_channels: int, dropout: float = 0.15):
        super().__init__()
        self.features = nn.Sequential(
            nn.Conv1d(input_channels, 64, kernel_size=5, padding=2),
            nn.BatchNorm1d(64),
            nn.GELU(),
            nn.Conv1d(64, 96, kernel_size=5, padding=4, dilation=2),
            nn.BatchNorm1d(96),
            nn.GELU(),
            nn.Conv1d(96, 128, kernel_size=3, padding=4, dilation=4),
            nn.BatchNorm1d(128),
            nn.GELU(),
            nn.Dropout(dropout),
        )
        self.head = nn.Sequential(
            nn.Linear(256, 96),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(96, 1),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        feat = self.features(x)
        avg = feat.mean(dim=-1)
        mx = feat.amax(dim=-1)
        pooled = torch.cat([avg, mx], dim=1)
        return self.head(pooled).squeeze(-1)


def build_model(
    input_dim: int,
    hidden_dims: tuple[int, ...] = (256, 128, 64),
    dropout: float = 0.15,
    model_type: str = "mlp",
) -> nn.Module:
    if model_type == "temporal_cnn":
        return TemporalEncounterCNN(input_channels=input_dim, dropout=dropout)
    return EncounterMLP(input_dim=input_dim, hidden_dims=hidden_dims, dropout=dropout)


def predict_probabilities(model: nn.Module, x: np.ndarray, batch_size: int = 4096, device: str = "cpu") -> np.ndarray:
    model.eval()
    out: list[np.ndarray] = []
    with torch.no_grad():
        for start in range(0, len(x), batch_size):
            batch = torch.from_numpy(x[start : start + batch_size]).to(device)
            logits = model(batch)
            probs = torch.sigmoid(logits).cpu().numpy()
            out.append(probs)
    if not out:
        return np.zeros(0, dtype=np.float32)
    return np.concatenate(out).astype(np.float32, copy=False)


def temporal_channel_columns() -> list[str]:
    return list(TEMPORAL_CHANNEL_COLUMNS)


def _load_local_module(module_name: str, relative_parts: tuple[str, ...]):
    import sys

    base = Path(__file__).resolve().parents[2]
    mod_path = base.joinpath(*relative_parts)
    spec = importlib.util.spec_from_file_location(module_name, mod_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load local module {module_name} from {mod_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _safe_demo_token(stem: str) -> str:
    token = re.sub(r"[^A-Za-z0-9]+", "_", str(stem).strip())
    token = re.sub(r"_+", "_", token).strip("_")
    return token or stem


def _load_match_for_demo_id(demo_id: str):
    cs2cd_adapter = _load_local_module("_nullcs_cs2cd_adapter", ("src", "adapters", "cs2cd_adapter.py"))
    demoparser2_local = _load_local_module("_nullcs_demoparser2_local", ("src", "adapters", "demoparser2_local.py"))
    build_mod = _load_local_module("_nullcs_build_cs2cd_engagement_features", ("src", "features", "build_cs2cd_engagement_features.py"))
    project_paths = _load_local_module("_nullcs_project_paths", ("src", "utils", "project_paths.py"))
    DEMOS_ROOT = project_paths.DEMOS_ROOT
    RAW_UPLOADS_ROOT = project_paths.RAW_UPLOADS_ROOT
    load_demoparser2_demo = demoparser2_local.load_demo

    if demo_id.startswith("CS2CD_PROLEGIT_"):
        meta_path = DEMOS_ROOT / demo_id / "meta.json"
        if not meta_path.exists():
            raise FileNotFoundError(f"Missing meta.json for {demo_id}")
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        source_demo = Path(str(meta.get("source_demo", "")))
        if not source_demo.exists():
            raise FileNotFoundError(f"Missing source demo for {demo_id}: {source_demo}")
        match = load_demoparser2_demo(source_demo, demo_id=demo_id)
    elif demo_id.startswith("CS2CD_"):
        prefix = "CS2CD_"
        suffix = demo_id[len(prefix) :]
        if suffix.startswith("no_cheater_present_"):
            split = "no_cheater_present"
            match_id = suffix[len("no_cheater_present_") :]
        elif suffix.startswith("with_cheater_present_"):
            split = "with_cheater_present"
            match_id = suffix[len("with_cheater_present_") :]
        else:
            raise ValueError(f"Unrecognized CS2CD demo_id split in temporal loader: {demo_id}")
        match = cs2cd_adapter.load_match(split, match_id)
    elif demo_id.startswith("TEST_") or demo_id.startswith("BENCH_"):
        demo_path = RAW_UPLOADS_ROOT / demo_id / f"{demo_id}.dem"
        if not demo_path.exists():
            raise FileNotFoundError(f"Missing raw uploaded demo for {demo_id}: {demo_path}")
        match = load_demoparser2_demo(demo_path, demo_id=demo_id)
    else:
        meta_path = DEMOS_ROOT / demo_id / "meta.json"
        if meta_path.exists():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            source_demo = Path(str(meta.get("source_demo", "")))
            if source_demo.exists():
                match = load_demoparser2_demo(source_demo, demo_id=demo_id)
            else:
                raise FileNotFoundError(f"Unsupported demo source for temporal model: {demo_id}")
        else:
            raise FileNotFoundError(f"Unsupported demo source for temporal model: {demo_id}")

    ticks = build_mod.prepare_ticks(match)
    tick_index = build_mod.build_tick_index(ticks)
    shots = match.shots.copy()
    starts = [int(x) for x in match.rounds["start_tick"].dropna().tolist()] if not match.rounds.empty else []
    if not shots.empty:
        if "shot_tick" in shots.columns:
            shots["round_num"] = shots["shot_tick"].apply(lambda t: cs2cd_adapter._assign_round_num(int(t), starts))
        else:
            shots["round_num"] = pd.Series(dtype="int64")
    else:
        shots["round_num"] = pd.Series(dtype="int64")
    shot_index = build_mod.build_shot_index(shots)
    damage_index = build_mod.build_pair_index(match.damages.copy(), "tick")
    return match, tick_index, shot_index, damage_index


def _resample_channel(values: np.ndarray, seq_len: int) -> np.ndarray:
    vals = np.asarray(values, dtype=np.float32).reshape(-1)
    if vals.size == 0:
        return np.zeros(seq_len, dtype=np.float32)
    if vals.size == 1:
        return np.full(seq_len, float(vals[0]), dtype=np.float32)
    src = np.linspace(0.0, 1.0, num=vals.size, dtype=np.float32)
    dst = np.linspace(0.0, 1.0, num=seq_len, dtype=np.float32)
    return np.interp(dst, src, vals).astype(np.float32, copy=False)


def build_temporal_sequences_for_demo(encounters: pd.DataFrame, seq_len: int = 32, channel_cols: list[str] | None = None) -> np.ndarray:
    build_mod = _load_local_module("_nullcs_build_cs2cd_engagement_features_seq", ("src", "features", "build_cs2cd_engagement_features.py"))

    if encounters.empty:
        cols = channel_cols or temporal_channel_columns()
        return np.zeros((0, len(cols), seq_len), dtype=np.float32)

    cols = channel_cols or temporal_channel_columns()
    demo_id = str(encounters["demo_id"].iloc[0])
    match, tick_index, shot_index, damage_index = _load_match_for_demo_id(demo_id)
    seqs = np.zeros((len(encounters), len(cols), seq_len), dtype=np.float32)

    def _event_distances(ticks: np.ndarray, event_ticks: set[int]) -> tuple[np.ndarray, np.ndarray]:
        if ticks.size == 0:
            empty = np.zeros(0, dtype=np.float32)
            return empty, empty
        if not event_ticks:
            missing = np.full(ticks.shape[0], float(seq_len * 8), dtype=np.float32)
            return missing, missing
        ev = np.asarray(sorted(int(t) for t in event_ticks), dtype=np.int32)
        idx = np.searchsorted(ev, ticks, side="left")
        next_vals = np.full(ticks.shape[0], float(seq_len * 8), dtype=np.float32)
        prev_vals = np.full(ticks.shape[0], float(seq_len * 8), dtype=np.float32)
        valid_next = idx < ev.size
        valid_prev = idx > 0
        if valid_next.any():
            next_vals[valid_next] = (ev[idx[valid_next]] - ticks[valid_next]).astype(np.float32, copy=False)
        if valid_prev.any():
            prev_vals[valid_prev] = (ticks[valid_prev] - ev[idx[valid_prev] - 1]).astype(np.float32, copy=False)
        return next_vals, prev_vals

    for row_idx, row in enumerate(encounters.itertuples(index=False)):
        attacker = str(getattr(row, "attacker_steamid")).strip()
        victim = str(getattr(row, "victim_steamid")).strip()
        round_num = int(getattr(row, "round_num"))
        start_tick = int(getattr(row, "start_tick"))
        end_tick = int(getattr(row, "end_tick"))
        tv = build_mod.build_pair_tick_table(tick_index, attacker, victim, round_num, start_tick, end_tick)
        if tv.empty:
            continue
        tv = build_mod.enrich_pair_ticks(tv)
        enc = tv[(tv["tick"] >= start_tick) & (tv["tick"] <= end_tick) & (tv["candidate"])].copy()
        if enc.empty:
            continue

        shot_rows = shot_index.get((attacker, round_num), pd.DataFrame(columns=["shot_tick"]))
        if not shot_rows.empty:
            shot_rows = shot_rows[(shot_rows["shot_tick"] >= start_tick) & (shot_rows["shot_tick"] <= end_tick)].copy()
        damage_rows = damage_index.get((attacker, victim, round_num), pd.DataFrame(columns=["tick"]))
        if not damage_rows.empty:
            damage_rows = damage_rows[(damage_rows["tick"] >= start_tick) & (damage_rows["tick"] <= end_tick)].copy()

        shot_ticks = set(pd.to_numeric(shot_rows.get("shot_tick"), errors="coerce").dropna().astype(int).tolist())
        damage_ticks = set(pd.to_numeric(damage_rows.get("tick"), errors="coerce").dropna().astype(int).tolist())
        tick_values = enc["tick"].astype(int).to_numpy(copy=False)

        aim_error = pd.to_numeric(enc.get("aim_error_deg"), errors="coerce").ffill().bfill().fillna(0.0).to_numpy(dtype=np.float32)
        target_yaw = pd.to_numeric(enc.get("target_yaw"), errors="coerce").fillna(0.0).to_numpy(dtype=np.float32)
        target_pitch = pd.to_numeric(enc.get("target_pitch"), errors="coerce").fillna(0.0).to_numpy(dtype=np.float32)
        a_yaw = pd.to_numeric(enc.get("a_yaw"), errors="coerce").fillna(0.0).to_numpy(dtype=np.float32)
        a_pitch = pd.to_numeric(enc.get("a_pitch"), errors="coerce").fillna(0.0).to_numpy(dtype=np.float32)
        cmd_yaw = pd.to_numeric(enc.get("a_cmd_yaw"), errors="coerce").ffill().bfill().fillna(0.0).to_numpy(dtype=np.float32)
        cmd_pitch = pd.to_numeric(enc.get("a_cmd_pitch"), errors="coerce").ffill().bfill().fillna(0.0).to_numpy(dtype=np.float32)

        aim_error_yaw_abs = np.abs(_wrap_deg_np(target_yaw - a_yaw)).astype(np.float32, copy=False)
        aim_error_pitch_abs = np.abs(_wrap_deg_np(target_pitch - a_pitch)).astype(np.float32, copy=False)
        aim_error_delta = np.diff(aim_error, prepend=aim_error[:1]).astype(np.float32, copy=False)
        aim_error_delta_abs = np.abs(aim_error_delta).astype(np.float32, copy=False)
        aim_error_accel = np.abs(np.diff(aim_error_delta, prepend=aim_error_delta[:1])).astype(np.float32, copy=False)

        cmd_yaw_delta = np.diff(cmd_yaw, prepend=cmd_yaw[:1]).astype(np.float32, copy=False)
        cmd_pitch_delta = np.diff(cmd_pitch, prepend=cmd_pitch[:1]).astype(np.float32, copy=False)
        cmd_view_gap_yaw = _wrap_deg_np(cmd_yaw - a_yaw).astype(np.float32, copy=False)
        cmd_view_gap_pitch = _wrap_deg_np(cmd_pitch - a_pitch).astype(np.float32, copy=False)

        ang_vel = np.zeros(tick_values.shape[0], dtype=np.float32)
        ang_jerk = np.zeros(tick_values.shape[0], dtype=np.float32)
        los_ang_vel = np.zeros(tick_values.shape[0], dtype=np.float32)
        los_ang_jerk = np.zeros(tick_values.shape[0], dtype=np.float32)
        for i in range(1, tick_values.shape[0]):
            dt = max(1, int(tick_values[i] - tick_values[i - 1]))
            av = np.hypot(float(_wrap_deg_np(np.array([a_yaw[i] - a_yaw[i - 1]], dtype=np.float32))[0]), float(_wrap_deg_np(np.array([a_pitch[i] - a_pitch[i - 1]], dtype=np.float32))[0])) / dt
            lv = np.hypot(float(_wrap_deg_np(np.array([target_yaw[i] - target_yaw[i - 1]], dtype=np.float32))[0]), float(_wrap_deg_np(np.array([target_pitch[i] - target_pitch[i - 1]], dtype=np.float32))[0])) / dt
            ang_vel[i] = float(av)
            los_ang_vel[i] = float(lv)
            if i >= 2:
                ang_jerk[i] = abs(float(av) - float(ang_vel[i - 1])) / dt
                los_ang_jerk[i] = abs(float(lv) - float(los_ang_vel[i - 1])) / dt

        v_spotted = build_mod._bool_series(enc.get("v_spotted", False), enc.index).astype(np.float32).to_numpy(dtype=np.float32)
        prev_vis = np.concatenate(([v_spotted[0]], v_spotted[:-1])) if v_spotted.size else np.zeros(0, dtype=np.float32)
        visible_transition_on = np.clip(v_spotted - prev_vis, 0.0, 1.0).astype(np.float32, copy=False)
        visible_transition_off = np.clip(prev_vis - v_spotted, 0.0, 1.0).astype(np.float32, copy=False)
        ticks_since_visible = np.zeros(tick_values.shape[0], dtype=np.float32)
        visible_run = 0.0
        for i, is_visible in enumerate(v_spotted):
            if is_visible >= 0.5:
                if i == 0 or prev_vis[i] < 0.5:
                    visible_run = 0.0
                else:
                    visible_run += max(1, int(tick_values[i] - tick_values[i - 1]))
                ticks_since_visible[i] = visible_run
            else:
                visible_run = 0.0

        a_scoped = build_mod._bool_series(enc.get("a_scoped", False), enc.index).astype(np.float32).to_numpy(dtype=np.float32)
        a_flashed = (pd.to_numeric(enc.get("a_flash"), errors="coerce").fillna(0.0).to_numpy(dtype=np.float32) > 0.0).astype(np.float32, copy=False)
        victim_flashed = (pd.to_numeric(enc.get("v_flash"), errors="coerce").fillna(0.0).to_numpy(dtype=np.float32) > 0.0).astype(np.float32, copy=False)

        ticks_to_next_shot, ticks_since_last_shot = _event_distances(tick_values, shot_ticks)
        ticks_to_next_damage, ticks_since_last_damage = _event_distances(tick_values, damage_ticks)

        attacker_speed = np.sqrt(
            np.square(pd.to_numeric(enc.get("a_vx"), errors="coerce").fillna(0.0).to_numpy(dtype=np.float32))
            + np.square(pd.to_numeric(enc.get("a_vy"), errors="coerce").fillna(0.0).to_numpy(dtype=np.float32))
            + np.square(pd.to_numeric(enc.get("a_vz"), errors="coerce").fillna(0.0).to_numpy(dtype=np.float32))
        )
        relative_speed = np.sqrt(
            np.square(pd.to_numeric(enc.get("v_vx"), errors="coerce").fillna(0.0).to_numpy(dtype=np.float32) - pd.to_numeric(enc.get("a_vx"), errors="coerce").fillna(0.0).to_numpy(dtype=np.float32))
            + np.square(pd.to_numeric(enc.get("v_vy"), errors="coerce").fillna(0.0).to_numpy(dtype=np.float32) - pd.to_numeric(enc.get("a_vy"), errors="coerce").fillna(0.0).to_numpy(dtype=np.float32))
            + np.square(pd.to_numeric(enc.get("v_vz"), errors="coerce").fillna(0.0).to_numpy(dtype=np.float32) - pd.to_numeric(enc.get("a_vz"), errors="coerce").fillna(0.0).to_numpy(dtype=np.float32))
        )
        feature_map: dict[str, np.ndarray] = {
            "aim_error_deg": aim_error,
            "aim_error_yaw_abs": aim_error_yaw_abs,
            "aim_error_pitch_abs": aim_error_pitch_abs,
            "aim_error_delta": aim_error_delta,
            "aim_error_delta_abs": aim_error_delta_abs,
            "aim_error_accel": aim_error_accel,
            "mouse_delta_abs": pd.to_numeric(enc.get("mouse_delta_abs"), errors="coerce").to_numpy(dtype=np.float32),
            "a_mdx": pd.to_numeric(enc.get("a_mdx"), errors="coerce").fillna(0.0).to_numpy(dtype=np.float32),
            "a_mdy": pd.to_numeric(enc.get("a_mdy"), errors="coerce").fillna(0.0).to_numpy(dtype=np.float32),
            "cmd_yaw_delta": cmd_yaw_delta,
            "cmd_pitch_delta": cmd_pitch_delta,
            "cmd_view_gap_yaw": cmd_view_gap_yaw,
            "cmd_view_gap_pitch": cmd_view_gap_pitch,
            "distance": pd.to_numeric(enc.get("distance"), errors="coerce").to_numpy(dtype=np.float32),
            "attacker_speed": attacker_speed.astype(np.float32, copy=False),
            "relative_speed": relative_speed.astype(np.float32, copy=False),
            "angular_velocity": ang_vel,
            "angular_jerk": ang_jerk,
            "los_angular_velocity": los_ang_vel,
            "los_angular_jerk": los_ang_jerk,
            "v_spotted": v_spotted,
            "visible_transition_on": visible_transition_on,
            "visible_transition_off": visible_transition_off,
            "ticks_since_visible": ticks_since_visible,
            "a_walking": build_mod._bool_series(enc.get("a_walking", False), enc.index).astype(np.float32).to_numpy(dtype=np.float32),
            "a_airborne": build_mod._bool_series(enc.get("a_airborne", False), enc.index).astype(np.float32).to_numpy(dtype=np.float32),
            "a_scoped": a_scoped,
            "a_flashed": a_flashed,
            "victim_flashed": victim_flashed,
            "shot_event": enc["tick"].astype(int).map(lambda t: 1.0 if int(t) in shot_ticks else 0.0).to_numpy(dtype=np.float32),
            "damage_event": enc["tick"].astype(int).map(lambda t: 1.0 if int(t) in damage_ticks else 0.0).to_numpy(dtype=np.float32),
            "ticks_to_next_shot": ticks_to_next_shot,
            "ticks_since_last_shot": ticks_since_last_shot,
            "ticks_to_next_damage": ticks_to_next_damage,
            "ticks_since_last_damage": ticks_since_last_damage,
        }
        for chan_idx, col in enumerate(cols):
            seqs[row_idx, chan_idx, :] = _resample_channel(feature_map.get(col, np.zeros(len(enc), dtype=np.float32)), seq_len)

    return seqs


def score_to_band(score: float) -> str:
    if score >= 0.8:
        return "very_high"
    if score >= 0.6:
        return "high"
    if score >= 0.4:
        return "moderate"
    if score >= 0.2:
        return "low"
    return "minimal"


def aggregate_encounter_scores(scored: pd.DataFrame) -> pd.DataFrame:
    if scored.empty:
        return pd.DataFrame(
            columns=[
                "demo_id",
                "attacker_steamid",
                "enn_score_mean",
                "enn_score_median",
                "enn_score_p90",
                "enn_score_max",
                "enn_score_top3_mean",
                "enn_score_std",
                "enn_high_rate",
                "enn_very_high_rate",
                "enn_hard_mean",
                "enn_low_vis_mean",
                "enn_kill_end_mean",
                "enn_score_concentration",
            ]
        )

    work = scored.copy()
    work["demo_id"] = work["demo_id"].astype(str)
    work["attacker_steamid"] = work["attacker_steamid"].astype(str).str.strip()
    work["encounter_nn_score"] = pd.to_numeric(work["encounter_nn_score"], errors="coerce").fillna(0.0)
    work["encounter_nn_hard"] = pd.to_numeric(work.get("encounter_nn_hard", 0.0), errors="coerce").fillna(0.0)
    work["encounter_nn_low_vis"] = pd.to_numeric(work.get("encounter_nn_low_vis", 0.0), errors="coerce").fillna(0.0)
    work["encounter_nn_kill_end"] = pd.to_numeric(work.get("encounter_nn_kill_end", 0.0), errors="coerce").fillna(0.0)

    rows: list[dict[str, object]] = []
    for (demo_id, steamid), g in work.groupby(["demo_id", "attacker_steamid"], sort=False):
        scores = pd.to_numeric(g["encounter_nn_score"], errors="coerce").fillna(0.0).sort_values(ascending=False)
        top3 = scores.head(3)
        total = float(scores.sum())
        concentration = float(top3.sum() / total) if total > 0 else 0.0
        hard_mask = g["encounter_nn_hard"] >= 0.5
        low_vis_mask = g["encounter_nn_low_vis"] >= 0.5
        rows.append(
            {
                "demo_id": str(demo_id),
                "attacker_steamid": str(steamid),
                "enn_score_mean": float(scores.mean()),
                "enn_score_median": float(scores.median()),
                "enn_score_p90": float(scores.quantile(0.90, interpolation="nearest")),
                "enn_score_max": float(scores.max()),
                "enn_score_top3_mean": float(top3.mean()) if not top3.empty else 0.0,
                "enn_score_std": float(scores.std(ddof=0)) if len(scores) > 1 else 0.0,
                "enn_high_rate": float((scores >= 0.6).mean()),
                "enn_very_high_rate": float((scores >= 0.8).mean()),
                "enn_hard_mean": float(scores[hard_mask.values].mean()) if hard_mask.any() else float(scores.mean()),
                "enn_low_vis_mean": float(scores[low_vis_mask.values].mean()) if low_vis_mask.any() else float(scores.mean()),
                "enn_kill_end_mean": float(scores[g["encounter_nn_kill_end"] >= 0.5].mean()) if (g["encounter_nn_kill_end"] >= 0.5).any() else float(scores.mean()),
                "enn_score_concentration": concentration,
            }
        )
    return pd.DataFrame(rows)


def save_feature_manifest(path: Path, feature_cols: list[str]) -> None:
    payload = {"feature_columns": feature_cols, "count": len(feature_cols)}
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def load_feature_manifest(path: Path) -> list[str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [str(x) for x in payload.get("feature_columns", [])]


def load_trained_encounter_model(model_path: Path, preproc_path: Path, features_path: Path, device: str = "cpu") -> tuple[nn.Module, EncounterPreprocessor, list[str], str]:
    payload = torch.load(model_path, map_location="cpu")
    feature_cols = load_feature_manifest(features_path)
    model_type = str(payload.get("model_type", "mlp"))
    preproc = TemporalSequencePreprocessor.load(preproc_path) if model_type == "temporal_cnn" else EncounterPreprocessor.load(preproc_path)
    hidden_dims = tuple(payload.get("hidden_dims", (256, 128, 64)))
    dropout = float(payload.get("dropout", 0.15))
    model = build_model(
        input_dim=int(payload.get("input_dim", len(feature_cols))),
        hidden_dims=hidden_dims,
        dropout=dropout,
        model_type=model_type,
    )
    model.load_state_dict(payload["state_dict"])
    device_name = "cuda" if device == "cuda" and torch.cuda.is_available() else "cpu"
    model = model.to(device_name)
    model.eval()
    setattr(model, "_nullcs_model_type", model_type)
    setattr(model, "_nullcs_seq_len", int(payload.get("seq_len", 32)))
    return model, preproc, feature_cols, device_name


def score_encounter_frame(
    df: pd.DataFrame,
    model: nn.Module,
    preproc,
    feature_cols: list[str],
    *,
    batch_size: int = 4096,
    device: str = "cpu",
) -> pd.DataFrame:
    work = df.copy()
    model_type = getattr(model, "_nullcs_model_type", "mlp")
    if model_type == "temporal_cnn":
        seq_len = int(getattr(model, "_nullcs_seq_len", getattr(preproc, "seq_len", 32)))
        raw = build_temporal_sequences_for_demo(work, seq_len=seq_len, channel_cols=feature_cols)
        x = preproc.transform_array(raw)
    else:
        x = preproc.transform_frame(work[feature_cols] if set(feature_cols).issubset(work.columns) else work)
    work["encounter_nn_score"] = predict_probabilities(model, x, batch_size=batch_size, device=device)
    work["encounter_nn_hard"] = (
        (pd.to_numeric(work.get("distance_mean"), errors="coerce").fillna(0.0) >= 900.0)
        | (pd.to_numeric(work.get("relative_speed_mean"), errors="coerce").fillna(0.0) >= 6.0)
        | (pd.to_numeric(work.get("visible_ratio"), errors="coerce").fillna(1.0) <= 0.75)
    ).astype(float)
    work["encounter_nn_low_vis"] = (pd.to_numeric(work.get("visible_ratio"), errors="coerce").fillna(1.0) <= 0.65).astype(float)
    work["encounter_nn_kill_end"] = pd.to_numeric(work.get("ended_in_kill_within_y"), errors="coerce").fillna(0.0)
    work["encounter_nn_band"] = work["encounter_nn_score"].map(score_to_band)
    return work

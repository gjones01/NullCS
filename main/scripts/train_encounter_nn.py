from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
import json
import math
from datetime import datetime
import os
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import torch
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.model_selection import GroupKFold
from torch import nn
from torch.utils.data import DataLoader, TensorDataset


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _load_local_module(module_name: str, relative_parts: tuple[str, ...]):
    import importlib.util

    mod_path = PROJECT_ROOT.joinpath(*relative_parts)
    spec = importlib.util.spec_from_file_location(module_name, mod_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load local module {module_name} from {mod_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


demo_labels_mod = _load_local_module("_nullcs_demo_labels", ("src", "utils", "demo_labels.py"))
project_paths_mod = _load_local_module("_nullcs_project_paths", ("src", "utils", "project_paths.py"))
training_mode_mod = _load_local_module("_nullcs_training_mode", ("src", "utils", "training_mode.py"))
encounter_nn_mod = _load_local_module("_nullcs_encounter_nn", ("src", "models", "encounter_nn.py"))

CHEATER_CSV = project_paths_mod.PROCESSED_ROOT / "CheaterSteamIDs.csv"
load_cheater_map = demo_labels_mod.load_cheater_map
label_demo_frame_pl = demo_labels_mod.label_demo_frame_pl
ensure_columns_pl = demo_labels_mod.ensure_columns_pl
DEMOS_ROOT = project_paths_mod.DEMOS_ROOT
MODELS_ROOT = project_paths_mod.MODELS_ROOT
PROCESSED_ROOT = project_paths_mod.PROCESSED_ROOT
REPORTS_ROOT = project_paths_mod.REPORTS_ROOT
resolve_train_data_mode = training_mode_mod.resolve_train_data_mode
source_of_demo_id = training_mode_mod.source_of_demo_id
aggregate_encounter_scores = encounter_nn_mod.aggregate_encounter_scores
build_temporal_sequences_for_demo = encounter_nn_mod.build_temporal_sequences_for_demo
build_model = encounter_nn_mod.build_model
encounter_model_artifacts = encounter_nn_mod.encounter_model_artifacts
encounter_player_feature_path = encounter_nn_mod.encounter_player_feature_path
encounter_report_artifacts = encounter_nn_mod.encounter_report_artifacts
fit_preprocessor = encounter_nn_mod.fit_preprocessor
fit_temporal_preprocessor = encounter_nn_mod.fit_temporal_preprocessor
predict_probabilities = encounter_nn_mod.predict_probabilities
save_feature_manifest = encounter_nn_mod.save_feature_manifest
select_encounter_feature_columns = encounter_nn_mod.select_encounter_feature_columns
temporal_channel_columns = encounter_nn_mod.temporal_channel_columns


RANDOM_STATE = 42


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Train encounter-level neural net and write OOF stacked features.")
    ap.add_argument("--train-data", default=None, help="Training data mode: local, cs2cd, or merged.")
    ap.add_argument("--model-type", default="temporal_cnn", choices=["mlp", "temporal_cnn"])
    ap.add_argument("--seq-len", type=int, default=32)
    ap.add_argument("--epochs", type=int, default=18)
    ap.add_argument("--batch-size", type=int, default=2048)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--weight-decay", type=float, default=1e-4)
    ap.add_argument("--patience", type=int, default=4)
    ap.add_argument("--device", default="cpu", choices=["cpu", "cuda"])
    ap.add_argument("--max-demos", type=int, default=None, help="Optional cap for quick smoke tests.")
    ap.add_argument("--rebuild-temporal-cache", action="store_true", help="Force rebuild of cached temporal tensors.")
    ap.add_argument(
        "--temporal-workers",
        type=int,
        default=3,
        help="Worker processes for temporal sequence cache building. Keep modest if you want the machine responsive.",
    )
    return ap.parse_args()


def _load_labeled_encounters(train_mode: str, max_demos: int | None = None) -> pd.DataFrame:
    cheater_map = load_cheater_map(CHEATER_CSV)
    files = sorted(DEMOS_ROOT.glob("*/encounters.parquet"))
    loaded_demos = 0
    frames: list[pd.DataFrame] = []
    for path in files:
        demo_id = path.parent.name
        source = source_of_demo_id(demo_id)
        if train_mode == "local" and source != "local_awpy":
            continue
        if train_mode == "cs2cd" and source != "cs2cd":
            continue
        if source not in {"local_awpy", "cs2cd"}:
            continue
        if max_demos is not None and loaded_demos >= max_demos:
            break
        raw = pd.read_parquet(path)
        if raw.empty:
            continue
        import polars as pl

        pl_df = pl.from_pandas(raw)
        labeled = label_demo_frame_pl(pl_df, demo_id, source, cheater_map)
        if labeled is None:
            continue
        labeled = ensure_columns_pl(
            labeled,
            [
                ("visible_ratio", np.nan),
                ("time_to_first_shot", np.nan),
                ("time_to_first_damage", np.nan),
                ("aim_error_at_first_visible", np.nan),
                ("aim_error_min", np.nan),
                ("aim_acquire_time", np.nan),
                ("aim_dwell_ticks", np.nan),
                ("shot_before_aim_acquire", False),
                ("shot_count", np.nan),
                ("shot_rate_per_128", np.nan),
                ("mean_shot_gap", np.nan),
                ("damage_count", np.nan),
                ("damage_total", np.nan),
                ("ended_in_damage", False),
                ("ended_in_kill_within_y", False),
                ("angular_velocity_mean", np.nan),
                ("angular_jerk_mean", np.nan),
                ("los_angular_velocity_mean", np.nan),
                ("los_angular_jerk_mean", np.nan),
                ("distance_mean", np.nan),
                ("closing_speed_mean", np.nan),
                ("attacker_speed_mean", np.nan),
                ("victim_speed_mean", np.nan),
                ("relative_speed_mean", np.nan),
                ("usercmd_mouse_dx", np.nan),
                ("usercmd_mouse_dy", np.nan),
            ],
        ).to_pandas()
        frames.append(labeled)
        loaded_demos += 1
    if not frames:
        raise RuntimeError("No labeled encounter frames found.")
    df = pd.concat(frames, ignore_index=True)
    df["label"] = pd.to_numeric(df["label"], errors="coerce").fillna(0).astype(int)
    df["demo_id"] = df["demo_id"].astype(str)
    df["attacker_steamid"] = df["attacker_steamid"].astype(str).str.strip()
    return df


def _make_loader(x: np.ndarray, y: np.ndarray, batch_size: int, shuffle: bool) -> DataLoader:
    ds = TensorDataset(torch.from_numpy(x), torch.from_numpy(y.astype(np.float32)))
    return DataLoader(ds, batch_size=batch_size, shuffle=shuffle, drop_last=False)


def _temporal_cache_paths(train_mode: str, seq_len: int) -> tuple[Path, Path]:
    stem = f"encounter_nn_{train_mode}_temporal_seq{seq_len}"
    return (
        PROCESSED_ROOT / f"{stem}.npz",
        MODELS_ROOT / f"{stem}_manifest.json",
    )


def _load_temporal_cache(df: pd.DataFrame, train_mode: str, seq_len: int, channel_cols: list[str]) -> np.ndarray | None:
    cache_path, manifest_path = _temporal_cache_paths(train_mode, seq_len)
    if not cache_path.exists() or not manifest_path.exists():
        return None
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        expected_demo_ids = df["demo_id"].astype(str).tolist()
        expected_attackers = df["attacker_steamid"].astype(str).tolist()
        if manifest.get("train_mode") != train_mode:
            return None
        if int(manifest.get("seq_len", -1)) != int(seq_len):
            return None
        if list(manifest.get("channel_cols", [])) != list(channel_cols):
            return None
        if int(manifest.get("rows", -1)) != int(len(df)):
            return None
        if manifest.get("demo_ids") != expected_demo_ids:
            return None
        if manifest.get("attacker_steamids") != expected_attackers:
            return None
        arr = np.load(cache_path)["temporal"]
        if arr.shape != (len(df), len(channel_cols), seq_len):
            return None
        print(f"[INFO] loaded temporal cache: {cache_path}")
        return arr.astype(np.float32, copy=False)
    except Exception as exc:
        print(f"[WARN] temporal cache ignored: {exc}")
        return None


def _save_temporal_cache(df: pd.DataFrame, train_mode: str, seq_len: int, channel_cols: list[str], arr: np.ndarray) -> None:
    cache_path, manifest_path = _temporal_cache_paths(train_mode, seq_len)
    np.savez_compressed(cache_path, temporal=np.asarray(arr, dtype=np.float32))
    manifest = {
        "train_mode": train_mode,
        "seq_len": int(seq_len),
        "channel_cols": list(channel_cols),
        "rows": int(len(df)),
        "demo_ids": df["demo_id"].astype(str).tolist(),
        "attacker_steamids": df["attacker_steamid"].astype(str).tolist(),
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "cache_path": str(cache_path),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"[OK] wrote temporal cache: {cache_path}")


def _build_temporal_tensor_worker(args: tuple[str, pd.DataFrame, int, list[str]]) -> tuple[str, np.ndarray]:
    demo_id, demo_df, seq_len, channel_cols = args
    demo_seq = build_temporal_sequences_for_demo(demo_df, seq_len=seq_len, channel_cols=channel_cols)
    return demo_id, demo_seq


def _build_temporal_tensor(df: pd.DataFrame, seq_len: int, channel_cols: list[str], temporal_workers: int = 1) -> np.ndarray:
    seqs = np.zeros((len(df), len(channel_cols), seq_len), dtype=np.float32)
    grouped: list[tuple[str, np.ndarray, pd.DataFrame]] = []
    for demo_id, group in df.groupby("demo_id", sort=False):
        demo_idx = group.index.to_numpy(dtype=np.int64, copy=False)
        demo_df = group.reset_index(drop=True)
        grouped.append((str(demo_id), demo_idx, demo_df))

    max_workers = max(1, min(int(temporal_workers), os.cpu_count() or 1))
    if max_workers <= 1 or len(grouped) <= 1:
        for demo_id, demo_idx, demo_df in grouped:
            demo_seq = build_temporal_sequences_for_demo(demo_df, seq_len=seq_len, channel_cols=channel_cols)
            if demo_seq.shape[0] != len(demo_idx):
                raise RuntimeError(
                    f"Temporal sequence build mismatch for {demo_id}: expected {len(demo_idx)} rows, got {demo_seq.shape[0]}"
                )
            seqs[demo_idx] = demo_seq
            print(f"[INFO] built temporal sequences for {demo_id}: rows={len(demo_idx)}")
        return seqs

    idx_map = {demo_id: demo_idx for demo_id, demo_idx, _ in grouped}
    print(f"[INFO] building temporal sequences with workers={max_workers}")
    executor_cls = ProcessPoolExecutor
    try:
        ex = executor_cls(max_workers=max_workers)
    except (PermissionError, OSError) as exc:
        print(f"[WARN] process workers unavailable ({exc}); falling back to threads")
        executor_cls = ThreadPoolExecutor
        ex = executor_cls(max_workers=max_workers)

    with ex:
        futures = {
            ex.submit(_build_temporal_tensor_worker, (demo_id, demo_df, seq_len, channel_cols)): demo_id
            for demo_id, _, demo_df in grouped
        }
        done = 0
        for fut in as_completed(futures):
            demo_id = futures[fut]
            demo_id_out, demo_seq = fut.result()
            demo_idx = idx_map[demo_id_out]
            if demo_seq.shape[0] != len(demo_idx):
                raise RuntimeError(
                    f"Temporal sequence build mismatch for {demo_id_out}: expected {len(demo_idx)} rows, got {demo_seq.shape[0]}"
                )
            seqs[demo_idx] = demo_seq
            done += 1
            print(f"[INFO] built temporal sequences for {demo_id_out}: rows={len(demo_idx)} demos_done={done}/{len(grouped)}")
    return seqs


def _fit_fold(
    train_df: pd.DataFrame,
    val_df: pd.DataFrame,
    x_train_raw: np.ndarray | None,
    x_val_raw: np.ndarray | None,
    feature_cols: list[str],
    args: argparse.Namespace,
) -> tuple[np.ndarray, dict[str, object], dict[str, object]]:
    if args.model_type == "temporal_cnn":
        if x_train_raw is None or x_val_raw is None:
            raise RuntimeError("Temporal model selected but raw sequence tensors were not provided.")
        preproc = fit_temporal_preprocessor(x_train_raw, feature_cols, seq_len=args.seq_len)
        x_train = preproc.transform_array(x_train_raw)
        x_val = preproc.transform_array(x_val_raw)
    else:
        preproc = fit_preprocessor(train_df, feature_cols)
        x_train = preproc.transform_frame(train_df)
        x_val = preproc.transform_frame(val_df)
    y_train = train_df["label"].to_numpy(dtype=np.float32)
    y_val = val_df["label"].to_numpy(dtype=np.float32)

    device = torch.device("cuda" if args.device == "cuda" and torch.cuda.is_available() else "cpu")
    model = build_model(input_dim=x_train.shape[1], model_type=args.model_type).to(device)
    pos = float((y_train == 1).sum())
    neg = float((y_train == 0).sum())
    pos_weight = torch.tensor([neg / max(1.0, pos)], dtype=torch.float32, device=device)
    loss_fn = nn.BCEWithLogitsLoss(pos_weight=pos_weight)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=args.weight_decay)

    train_loader = _make_loader(x_train, y_train, args.batch_size, shuffle=True)
    best_state: dict[str, torch.Tensor] | None = None
    best_ap = -1.0
    best_epoch = 0
    stale = 0

    for epoch in range(1, args.epochs + 1):
        model.train()
        for xb, yb in train_loader:
            xb = xb.to(device)
            yb = yb.to(device)
            optimizer.zero_grad(set_to_none=True)
            logits = model(xb)
            loss = loss_fn(logits, yb)
            loss.backward()
            optimizer.step()

        val_probs = predict_probabilities(model, x_val, batch_size=args.batch_size, device=str(device))
        try:
            val_ap = float(average_precision_score(y_val, val_probs))
        except Exception:
            val_ap = 0.0
        if val_ap > best_ap + 1e-4:
            best_ap = val_ap
            best_epoch = epoch
            stale = 0
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
        else:
            stale += 1
            if stale >= args.patience:
                break

    if best_state is not None:
        model.load_state_dict(best_state)
    final_probs = predict_probabilities(model, x_val, batch_size=args.batch_size, device=str(device))
    fold_metrics = {
        "average_precision": float(average_precision_score(y_val, final_probs)),
        "roc_auc": float(roc_auc_score(y_val, final_probs)) if len(np.unique(y_val)) > 1 else float("nan"),
        "best_epoch": int(best_epoch),
    }
    model_payload = {
        "state_dict": {k: v.detach().cpu() for k, v in model.state_dict().items()},
        "preprocessor": preproc,
    }
    return final_probs, fold_metrics, model_payload


def _fit_full_model(
    df: pd.DataFrame,
    feature_cols: list[str],
    epochs: int,
    args: argparse.Namespace,
    raw_x: np.ndarray | None = None,
) -> tuple[dict[str, torch.Tensor], object]:
    if args.model_type == "temporal_cnn":
        if raw_x is None:
            raw_x = _build_temporal_tensor(df, seq_len=args.seq_len, channel_cols=feature_cols, temporal_workers=args.temporal_workers)
        preproc = fit_temporal_preprocessor(raw_x, feature_cols, seq_len=args.seq_len)
        x = preproc.transform_array(raw_x)
    else:
        preproc = fit_preprocessor(df, feature_cols)
        x = preproc.transform_frame(df)
    y = df["label"].to_numpy(dtype=np.float32)
    device = torch.device("cuda" if args.device == "cuda" and torch.cuda.is_available() else "cpu")
    model = build_model(input_dim=x.shape[1], model_type=args.model_type).to(device)
    pos = float((y == 1).sum())
    neg = float((y == 0).sum())
    pos_weight = torch.tensor([neg / max(1.0, pos)], dtype=torch.float32, device=device)
    loss_fn = nn.BCEWithLogitsLoss(pos_weight=pos_weight)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=args.weight_decay)
    loader = _make_loader(x, y, args.batch_size, shuffle=True)
    for _ in range(max(1, epochs)):
        model.train()
        for xb, yb in loader:
            xb = xb.to(device)
            yb = yb.to(device)
            optimizer.zero_grad(set_to_none=True)
            logits = model(xb)
            loss = loss_fn(logits, yb)
            loss.backward()
            optimizer.step()
    state = {k: v.detach().cpu() for k, v in model.state_dict().items()}
    return state, preproc


def _augment_scored_encounters(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["encounter_nn_hard"] = (
        (pd.to_numeric(out.get("distance_mean"), errors="coerce").fillna(0.0) >= 900.0)
        | (pd.to_numeric(out.get("relative_speed_mean"), errors="coerce").fillna(0.0) >= 6.0)
        | (pd.to_numeric(out.get("visible_ratio"), errors="coerce").fillna(1.0) <= 0.75)
    ).astype(float)
    out["encounter_nn_low_vis"] = (pd.to_numeric(out.get("visible_ratio"), errors="coerce").fillna(1.0) <= 0.65).astype(float)
    out["encounter_nn_kill_end"] = pd.to_numeric(out.get("ended_in_kill_within_y"), errors="coerce").fillna(0.0)
    return out


def main() -> int:
    args = parse_args()
    train_mode = resolve_train_data_mode(args.train_data)
    df = _load_labeled_encounters(train_mode, max_demos=args.max_demos)
    feature_cols = temporal_channel_columns() if args.model_type == "temporal_cnn" else select_encounter_feature_columns(df)
    if not feature_cols:
        raise RuntimeError("No encounter feature columns selected for neural net training.")
    raw_temporal = None
    if args.model_type == "temporal_cnn":
        if not args.rebuild_temporal_cache:
            raw_temporal = _load_temporal_cache(df, train_mode, args.seq_len, feature_cols)
        if raw_temporal is None:
            raw_temporal = _build_temporal_tensor(
                df,
                seq_len=args.seq_len,
                channel_cols=feature_cols,
                temporal_workers=args.temporal_workers,
            )
            _save_temporal_cache(df, train_mode, args.seq_len, feature_cols, raw_temporal)
        print(f"[INFO] temporal tensor shape={raw_temporal.shape}")

    groups = df["demo_id"].astype(str).to_numpy()
    y = df["label"].to_numpy()
    n_groups = int(pd.Series(groups).nunique())
    n_splits = min(5, n_groups)
    if n_splits < 2:
        raise RuntimeError(f"Encounter NN training needs at least 2 unique demo groups, found {n_groups}.")
    cv = GroupKFold(n_splits=n_splits)
    oof = np.zeros(len(df), dtype=np.float32)
    fold_summaries: list[dict[str, object]] = []
    best_epochs: list[int] = []

    split_x = raw_temporal if raw_temporal is not None else df[feature_cols]
    for fold_id, (train_idx, val_idx) in enumerate(cv.split(split_x, y, groups=groups), start=1):
        train_df = df.iloc[train_idx].copy()
        val_df = df.iloc[val_idx].copy()
        x_train_raw = raw_temporal[train_idx] if raw_temporal is not None else None
        x_val_raw = raw_temporal[val_idx] if raw_temporal is not None else None
        val_probs, metrics, _payload = _fit_fold(train_df, val_df, x_train_raw, x_val_raw, feature_cols, args)
        oof[val_idx] = val_probs
        metrics["fold_id"] = fold_id
        metrics["train_rows"] = int(len(train_df))
        metrics["val_rows"] = int(len(val_df))
        fold_summaries.append(metrics)
        best_epochs.append(int(metrics["best_epoch"]))
        print(f"[FOLD {fold_id}] AP={metrics['average_precision']:.4f} ROC={metrics['roc_auc']:.4f} best_epoch={metrics['best_epoch']}")

    oof_ap = float(average_precision_score(y, oof))
    oof_roc = float(roc_auc_score(y, oof))
    print(f"[OOF] AP={oof_ap:.4f} ROC={oof_roc:.4f}")

    reports = encounter_report_artifacts(REPORTS_ROOT, train_mode)
    scored_encounters = df.copy()
    scored_encounters["encounter_nn_score"] = oof
    scored_encounters = _augment_scored_encounters(scored_encounters)
    scored_encounters.to_parquet(reports["oof_encounters_parquet"], index=False)
    scored_encounters.to_csv(reports["oof_encounters_csv"], index=False)

    player_scores = aggregate_encounter_scores(scored_encounters)
    player_scores.to_parquet(reports["oof_players_parquet"], index=False)
    player_scores.to_csv(reports["oof_players_csv"], index=False)
    player_feature_path = encounter_player_feature_path(PROCESSED_ROOT, train_mode)
    player_scores.to_parquet(player_feature_path, index=False)

    final_epochs = int(np.median(best_epochs)) if best_epochs else max(1, args.epochs // 2)
    final_state, final_preproc = _fit_full_model(df, feature_cols, final_epochs, args, raw_x=raw_temporal)
    artifacts = encounter_model_artifacts(MODELS_ROOT, train_mode)
    MODELS_ROOT.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "state_dict": final_state,
            "input_dim": len(feature_cols),
            "hidden_dims": (256, 128, 64),
            "dropout": 0.15,
            "model_type": args.model_type,
            "seq_len": args.seq_len,
            "train_data_mode": train_mode,
        },
        artifacts["model"],
    )
    final_preproc.save(artifacts["preproc"])
    save_feature_manifest(artifacts["features"], feature_cols)

    manifest = {
        "train_data_mode": train_mode,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "max_demos": args.max_demos,
        "rows": int(len(df)),
        "demos": int(df["demo_id"].nunique()),
        "positive": int((df["label"] == 1).sum()),
        "negative": int((df["label"] == 0).sum()),
        "feature_count": len(feature_cols),
        "model_type": args.model_type,
        "seq_len": args.seq_len,
        "oof_average_precision": oof_ap,
        "oof_roc_auc": oof_roc,
        "selected_final_epochs": final_epochs,
        "folds": fold_summaries,
        "artifacts": {k: str(v) for k, v in artifacts.items()},
        "reports": {k: str(v) for k, v in reports.items()},
        "player_feature_path": str(player_feature_path),
    }
    artifacts["manifest"].write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(f"[OK] wrote {artifacts['model']}")
    print(f"[OK] wrote {artifacts['features']}")
    print(f"[OK] wrote {artifacts['preproc']}")
    print(f"[OK] wrote {artifacts['manifest']}")
    print(f"[OK] wrote {player_feature_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

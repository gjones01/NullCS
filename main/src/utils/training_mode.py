from __future__ import annotations

import os
from pathlib import Path


TRAIN_DATA_MODES = ("local", "cs2cd", "merged")


def normalize_train_data_mode(value: str | None) -> str:
    mode = str(value or "").strip().lower() or "cs2cd"
    if mode not in TRAIN_DATA_MODES:
        raise ValueError(f"Unsupported train-data mode '{mode}'. Expected one of: {TRAIN_DATA_MODES}")
    return mode


def resolve_train_data_mode(cli_value: str | None = None) -> str:
    if cli_value:
        return normalize_train_data_mode(cli_value)
    return normalize_train_data_mode(os.getenv("NULLCS_TRAIN_DATA", os.getenv("CLARITY_TRAIN_DATA", "cs2cd")))


def model_stem_for_mode(mode: str) -> str:
    normalized = normalize_train_data_mode(mode)
    return f"xgb_player_level_{normalized}"


def player_features_path(processed_root: Path, mode: str) -> Path:
    normalized = normalize_train_data_mode(mode)
    if normalized == "merged":
        return processed_root / "player_features.parquet"
    return processed_root / f"player_features_{normalized}.parquet"


def player_features_summary_path(processed_root: Path, mode: str) -> Path:
    normalized = normalize_train_data_mode(mode)
    if normalized == "merged":
        return processed_root / "player_features_summary.json"
    return processed_root / f"player_features_{normalized}_summary.json"


def model_artifact_paths(models_root: Path, mode: str) -> dict[str, Path]:
    stem = model_stem_for_mode(mode)
    return model_artifact_paths_for_stem(models_root, stem)


def model_artifact_paths_for_stem(models_root: Path, stem: str) -> dict[str, Path]:
    return {
        "model": models_root / f"{stem}.json",
        "features": models_root / f"{stem}_features.txt",
        "grid_results": models_root / f"{stem}_gridcv_results.csv",
        "best_params": models_root / f"{stem}_best_params.json",
        "training_manifest": models_root / f"{stem}_training_manifest.json",
        "eval_summary": models_root / f"{stem}_eval_summary.json",
        "calibrator": models_root / f"{stem}_calibration.pkl",
        "calibration_summary": models_root / f"{stem}_calibration_summary.json",
        "calibration_curve": models_root / f"{stem}_calibration_curve.csv",
    }


def default_feature_list_path(models_root: Path, mode: str, artifact_stem: str | None = None) -> Path | None:
    """Feature-list contract that training/evaluation lock onto by default.

    Resolution order: the **mode contract** file first (for CS2CD that is
    ``xgb_player_level_cs2cd_features.txt``, the 449-feature list), otherwise the
    explicit ``artifact_stem`` feature file. Returns ``None`` when neither
    exists, which keeps the legacy auto-select behaviour for modes that never
    published a list.

    The mode contract deliberately outranks a stem-local list: a stem file can be
    a byproduct of an earlier unlocked run (verified: an unlocked run wrote a
    463-feature ``<stem>_features.txt`` that then silently replaced the 449
    contract). Experiments that intentionally train a different feature set must
    pass ``--feature-list-path`` explicitly, which is recorded in the manifest.

    Guards AUDIT.md finding F3: without this, training silently selected every
    numeric column and changed the feature contract.
    """
    candidates: list[Path] = [model_artifact_paths(models_root, mode)["features"]]
    stem = str(artifact_stem or "").strip()
    if stem:
        candidates.append(models_root / f"{stem}_features.txt")
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def report_artifact_paths(reports_root: Path, mode: str) -> dict[str, Path]:
    normalized = normalize_train_data_mode(mode)
    suffix = "" if normalized == "merged" else f"_{normalized}"
    return report_artifact_paths_for_suffix(reports_root, suffix)


def report_artifact_paths_for_suffix(reports_root: Path, suffix: str) -> dict[str, Path]:
    return {
        "ranked_player_oof": reports_root / f"ranked_player_demo_suspicion_oof{suffix}.csv",
        "ranked_demo_oof": reports_root / f"ranked_demo_suspicion_oof{suffix}.csv",
        "player_oof_csv": reports_root / f"player_oof_predictions{suffix}.csv",
        "player_oof_parquet": reports_root / f"player_oof_predictions{suffix}.parquet",
        "top1_misses": reports_root / f"top1_misses{suffix}.csv",
    }


def source_of_demo_id(demo_id: str) -> str:
    demo = str(demo_id)
    if demo.startswith(("CDemo", "Normal", "Pro")):
        return "local_awpy"
    if demo.startswith("CS2CD_"):
        return "cs2cd"
    if demo.startswith("TEST_"):
        return "test_infer"
    return "other"

from __future__ import annotations

import os
from pathlib import Path


# Canonical inference artifact (owner decision D2, AUDIT.md "Decision answers").
# Inference must load this stem unless an explicit artifact is requested via
# resolve_model_artifacts(model_artifact=...), NULLCS_MODEL_ARTIFACT or
# CLARITY_MODEL_ARTIFACT. Override the pinned stem itself with
# NULLCS_DEFAULT_MODEL_STEM / CLARITY_DEFAULT_MODEL_STEM when running experiments.
DEFAULT_MODEL_STEM = "xgb_player_level_cs2cd"


def default_model_stem() -> str:
    override = os.environ.get("NULLCS_DEFAULT_MODEL_STEM") or os.environ.get("CLARITY_DEFAULT_MODEL_STEM")
    stem = str(override or "").strip()
    return stem or DEFAULT_MODEL_STEM


def _candidate_models(models_dir: Path) -> list[Path]:
    bad_tokens = ("best_params", "gridcv_results", "calibrator", "summary", "manifest", "curve", "report")
    out = []
    for p in models_dir.glob("*.json"):
        name = p.name.lower()
        if not name.startswith("xgb_"):
            continue
        if any(tok in name for tok in bad_tokens):
            continue
        out.append(p)
    return sorted(out, key=lambda x: x.stat().st_mtime, reverse=True)


def resolve_model_artifacts(models_dir: Path, model_artifact: str | None = None) -> tuple[Path, Path]:
    models_dir = Path(models_dir)
    if model_artifact:
        model_path = Path(model_artifact)
        if not model_path.is_absolute():
            model_path = models_dir / model_path
    else:
        pinned = models_dir / f"{default_model_stem()}.json"
        if pinned.exists():
            model_path = pinned
        else:
            # Fallback only: newest-mtime selection is a legacy behaviour kept so
            # an explicitly renamed/removed canonical artifact cannot hard-fail
            # inference. Experiments must pin their artifact explicitly.
            candidates = _candidate_models(models_dir)
            if not candidates:
                raise FileNotFoundError(f"No model artifacts found in {models_dir}")
            model_path = candidates[0]

    if not model_path.exists():
        raise FileNotFoundError(f"Model artifact not found: {model_path}")

    stem = model_path.stem
    sibling_feat = model_path.with_name(f"{stem}_features.txt")
    default_feat = models_dir / "xgb_player_level_features.txt"
    if sibling_feat.exists():
        feat_path = sibling_feat
    elif default_feat.exists():
        feat_path = default_feat
    else:
        feature_candidates = sorted(models_dir.glob("*features*.txt"), key=lambda x: x.stat().st_mtime, reverse=True)
        if not feature_candidates:
            raise FileNotFoundError(f"No feature list artifact found in {models_dir}")
        feat_path = feature_candidates[0]

    return model_path, feat_path

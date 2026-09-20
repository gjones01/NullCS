from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import sys

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path = [p for p in sys.path if "ClarityCS\\main" not in str(p)]
if str(PROJECT_ROOT) in sys.path:
    sys.path.remove(str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT))
for mod_name in list(sys.modules):
    if mod_name == "src" or mod_name.startswith("src."):
        sys.modules.pop(mod_name, None)
src_init = PROJECT_ROOT / "src" / "__init__.py"
src_spec = importlib.util.spec_from_file_location("src", src_init, submodule_search_locations=[str(PROJECT_ROOT / "src")])
if src_spec is None or src_spec.loader is None:
    raise RuntimeError(f"Could not bootstrap local src package from {src_init}")
src_module = importlib.util.module_from_spec(src_spec)
sys.modules["src"] = src_module
src_spec.loader.exec_module(src_module)

from src.models.encounter_nn import (
    aggregate_encounter_scores,
    encounter_infer_player_feature_path,
    encounter_model_artifacts,
    load_trained_encounter_model,
    score_encounter_frame,
)
from src.utils.project_paths import DEMOS_ROOT, MODELS_ROOT, PROCESSED_ROOT
from src.utils.training_mode import resolve_train_data_mode


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Score encounter rows with the trained encounter NN.")
    ap.add_argument("--train-data", default=None, help="Training data mode for artifact selection.")
    ap.add_argument("--demo-id", default=None, help="Optional single demo id. When omitted, scores all demos.")
    ap.add_argument("--device", default="cpu", choices=["cpu", "cuda"])
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    train_mode = resolve_train_data_mode(args.train_data)
    artifacts = encounter_model_artifacts(MODELS_ROOT, train_mode)
    if not artifacts["model"].exists():
        raise FileNotFoundError(f"Encounter NN model not found: {artifacts['model']}")
    model, preproc, feature_cols, device_name = load_trained_encounter_model(
        artifacts["model"], artifacts["preproc"], artifacts["features"], device=args.device
    )

    demo_dirs = []
    if args.demo_id:
        demo_dirs = [DEMOS_ROOT / args.demo_id]
    else:
        demo_dirs = sorted(DEMOS_ROOT.glob("*"))

    for demo_dir in demo_dirs:
        enc_path = demo_dir / "encounters.parquet"
        if not enc_path.exists():
            continue
        df = pd.read_parquet(enc_path)
        if df.empty:
            continue
        scored = score_encounter_frame(df, model, preproc, feature_cols, device=device_name)
        scored_path = demo_dir / "encounter_nn_scores.parquet"
        scored.to_parquet(scored_path, index=False)
        player_scores = aggregate_encounter_scores(scored)
        player_scores_path = encounter_infer_player_feature_path(PROCESSED_ROOT, demo_dir.name)
        player_scores.to_parquet(player_scores_path, index=False)
        manifest = {
            "demo_id": demo_dir.name,
            "encounter_model": str(artifacts["model"]),
            "scored_encounters": str(scored_path),
            "player_scores": str(player_scores_path),
        }
        (demo_dir / "encounter_nn_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        print(f"[OK] scored encounter NN for {demo_dir.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

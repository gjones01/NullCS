# Pipeline

Practical map for rebuilding the public artifacts. All paths are relative to the
repository root, and commands are meant to be run from there.

## Data flow

```text
raw demos
  -> parsed per-demo zips (parquet tables)
  -> engagement rows per demo
  -> encounter windows and window-model scores
  -> player-demo feature table
  -> grouped model training
  -> out-of-fold reports and ranked review output
```

## Commands

Parse, build features, aggregate, train, evaluate:

```powershell
python main/src/parse/parse_demos_awpy_api.py
python main/src/features/build_engagement_features.py
python main/src/features/aggregate_player_features.py
python main/scripts/train_xgb_gridcv.py
python main/scripts/evaluate_xgb_gridcv.py
```

Inference and explanation:

```powershell
python main/scripts/run_infer_pipeline.py --dem_path path\to\match.dem
python main/scripts/infer_demo_from_path.py --dem path\to\match.dem
python main/scripts/explain_demo.py --demo CDemo3
python main/scripts/explain_demo.py --demo CDemo3 --steamid 76561198762460140
```

`run_infer_pipeline.py` is the full inference path (it also scores encounter
windows). `infer_demo_from_path.py` is the lighter single-demo CLI.

## Key artifacts

| Artifact | What it is |
| --- | --- |
| `main/data/processed/demos/<demo_id>/engagement_features.parquet` | one row per engagement |
| `main/data/processed/player_features_cs2cd.parquet` | player-demo feature table |
| `main/data/processed/models/xgb_player_level_cs2cd.json` | model used by inference (pinned) |
| `main/data/processed/models/xgb_player_level_cs2cd_features.txt` | the 449-feature contract |
| `main/data/processed/models/xgb_player_level_cs2cd_eval_summary.json` | saved evaluation summary |
| `main/data/processed/models/encounter_nn_cs2cd_training_manifest.json` | window-model summary |
| `main/data/processed/reports/encounter_nn_cs2cd_oof_encounters.parquet` | window scores, out-of-fold |
| `main/data/processed/reports/ranked_player_demo_suspicion_oof_cs2cd.csv` | ranked players plus evidence |
| `main/data/processed/reports/ranked_demo_suspicion_oof_cs2cd.csv` | ranked demos, top-k summary |

## House rules worth knowing

- Inference loads the pinned artifact (`xgb_player_level_cs2cd`). Point it elsewhere
  with `--model-artifact`, `NULLCS_MODEL_ARTIFACT` or `NULLCS_DEFAULT_MODEL_STEM`.
- Training locks the feature list to the mode contract by default. Use
  `--feature-list-path` to pin a different list, or `--no-feature-list-lock` for the
  old auto-select behaviour.
- `GroupKFold` groups by `demo_id`. It is not a chronological split.
- Evaluation retrains fold models to produce out-of-fold numbers; only inference
  loads a saved model.
- Some older scripts still use hardcoded absolute paths.
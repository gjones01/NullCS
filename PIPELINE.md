# Pipeline

This file is the practical map for rebuilding the public artifacts. Paths are relative to the repository root.

## Main Data Flow

```text
raw demos
  -> parsed zip/parquet tables
  -> canonical events and engagement rows
  -> encounter windows
  -> temporal CNN encounter scores
  -> player-demo feature table
  -> grouped model training
  -> OOF reports and ranked review outputs
```

## Core Commands

```powershell
python main/src/parse/parse_demos_awpy_api.py
python main/src/features/build_engagement_features.py
python main/src/features/aggregate_player_features.py
python main/scripts/train_xgb_gridcv.py
python main/scripts/evaluate_xgb_gridcv.py
```

Explain one demo/player:

```powershell
python main/scripts/explain_demo.py --demo CDemo3
python main/scripts/explain_demo.py --demo CDemo3 --steamid 76561198762460140
```

## Key Artifacts

| Artifact | Purpose |
| --- | --- |
| `main/data/processed/player_features_cs2cd.parquet` | CS2CD-enriched player-demo features before evaluation filters |
| `main/data/processed/reports/encounter_nn_cs2cd_oof_encounters.parquet` | Encounter-level OOF CNN scores |
| `main/data/processed/reports/ranked_player_demo_suspicion_oof_cs2cd.csv` | Player-level OOF rankings and evidence columns |
| `main/data/processed/reports/ranked_demo_suspicion_oof_cs2cd.csv` | Demo-level top-k ranking summary |
| `main/data/processed/models/encounter_nn_cs2cd_training_manifest.json` | Encounter CNN training summary |
| `main/data/processed/models/xgb_player_level_cs2cd_eval_summary.json` | Player-level evaluation summary |
| `main/data/processed/models/xgb_player_level_cs2cd_features.txt` | 449-feature list |

## Current Gotchas

- Some scripts still use hardcoded paths.
- GroupKFold is grouped by `demo_id`; it is not a chronological future split.
- Evaluation scripts may retrain fold models for OOF reporting rather than loading only one saved model.
- Public scores are review-priority signals. They should not be presented as enforcement probabilities.

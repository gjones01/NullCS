# ClarityCS Agent Context (Verified From Code)

## 1) Workspace Tree (2-3 levels)

Root (`C:\NullCS`):
- Directories:
  - `CheaterDemos/`
  - `cheat_training/`
  - `datasets/`
  - `Demos/`
  - `LegitDemos/`
  - `legit_baseline_outputs/`
  - `main/`
  - `model/`
  - `NewAnubisTri/`
  - `outputs/`
  - `parsed_zips/`
  - `Plots/`
  - `Post 100 Scripts New/`
  - `processed/`
  - `raw_parsed/`
  - `raw_zips/`
  - `Tick Level/`
  - `tris/`
  - `__pycache__/`
- Root files:
  - `AGENTS.md`
  - `engagement_features.py`
  - `extract_and_rename_pro_demos.py`
  - `LegitvsBlatantCurves.py`
  - `parse_demo.py`
  - `preaim_through_wall.py`
  - `run_batch.py`
  - plus image artifacts (`*.png`) and `Normal001.zip`

`main/` (authoritative current pipeline code):
- `main/data/`
  - `main/data/parse_zips/`
  - `main/data/processed/`
    - `main/data/processed/CheaterSteamIDs.csv`
    - `main/data/processed/player_features.parquet`
    - `main/data/processed/demos/`
      - contains `CDemo1..CDemo20`, `Normal001..Normal100`, `Pro001..Pro100` (220 dirs total)
      - each demo dir contains: `events.parquet`, `engagement_features.parquet`, `meta.json`
    - `main/data/processed/models/`
      - `xgb_player_level_gridcv.json`
      - `xgb_player_level_features.txt`
      - `xgb_gridcv_results.csv`
    - `main/data/processed/reports/`
      - `ranked_player_demo_suspicion.csv`
      - `ranked_demo_suspicion.csv`
      - per-demo/per-player explain outputs (for demos already explained)
- `main/scripts/`
  - `train_xgb_gridcv.py`
  - `evaluate_xgb_gridcv.py`
  - `explain_demo.py`
  - `run_pipeline.py`
- `main/src/`
  - `main/src/parse/`
    - `parse_demos_awpy_api.py`
    - `build_events_from_zips.py`
  - `main/src/features/`
    - `build_engagement_features.py`
    - `aggregate_player_features.py`
  - `main/src/utils/`
    - `visibility_awpy.py`, `awpy_map_assets.py`, `explain_demo.py`, etc.
  - `main/src/models/` (present as a directory, no files discovered in this scan)

Other major data/code branches in workspace:
- `parsed_zips/`: contains 220 zip demos (`CDemo1..20`, `Normal001..100`, `Pro001..100`).
- `cheat_training/`: legacy/alternate pipeline caches and model artifacts.
  - `cheat_training/artifacts_cheat/`
  - `cheat_training/cache_aim_windows/` with demo subdirs (`Demo1..20`, `Normal001..100`, `Pro001..100`)
  - `cheat_training/cache_parsed/` with same subdir pattern
  - `cheat_training/cache_kill_features/`
- `raw_parsed/`: alternate parsed parquet tree.
  - `raw_parsed/normal/Normal001..Normal100/`
  - `raw_parsed/pro/Pro001..Pro100/`
  - `raw_parsed/samples_csv/`
- `Tick Level/`: alternate scripts (`parse_all_demos.py`, `build_aim_windows_all.py`, `train_xgb_is_cheater.py`, etc.)
- `Plots/scripts/` and `Post 100 Scripts New/`: older/side scripts.

## 2) Exact Parse -> Build -> Features -> Train -> Eval -> Aggregation Entry Points

This section lists exact script files, functions, and paths used by current `main` code.

### Step A: Parse demos into zipped parquet bundles
- File: `main/src/parse/parse_demos_awpy_api.py`
- Entrypoint function: `main() -> int`
- Key functions:
  - `list_demos(root: Path) -> list[Path]`
  - `parse_one(demo_path: Path) -> bool`
  - `write_df_to_parquet(df, path: Path) -> None`
- Input paths (constants):
  - `NORMAL_DIR = C:\NullCS\LegitDemos\NormalRenamed`
  - `PRO_DIR = C:\NullCS\LegitDemos\ProsRenamed`
  - `CHEATER_DIR = C:\NullCS\CheaterDemos`
- Output path:
  - `OUT_ROOT = C:\NullCS\parsed_zips`
  - per demo output: `C:\NullCS\parsed_zips\<DemoStem>.zip`
- Zip contents written by code:
  - tries to include `kills.parquet`, `damages.parquet`, `shots.parquet`, `grenades.parquet`, `smokes.parquet`, `infernos.parquet`, `bomb.parquet`, `ticks.parquet`, `rounds.parquet`, `footsteps.parquet` (optional if missing)
  - always writes `header.json`
- CLI args: none (hardcoded constants only)

### Step B: Build canonical events parquet from zipped parses
- File: `main/src/parse/build_events_from_zips.py`
- Entrypoint function: `main()`
- Key functions:
  - `build_events_for_zip(zip_path: Path) -> bool`
  - `read_parquet_from_zip(z, name) -> pl.DataFrame`
  - `read_json_from_zip(z, name) -> dict`
  - `safe_get(d, keys, default=None)`
- Input path:
  - `ZIPS_DIR = C:\NullCS\parsed_zips`
- Output path (note: different root than `main/data/processed`):
  - `OUT_ROOT = C:\NullCS\processed\demos`
  - per demo: `C:\NullCS\processed\demos\<demo_id>\events.parquet`
  - per demo metadata: `...\meta.json`
- Canonical events columns written:
  - `demo_id`, `event_id`, `event_type`, `tick`, `round_num`, `attacker_steamid`, `victim_steamid`, `is_headshot`, `weapon`, `map_name`
- CLI args: none (hardcoded constants only)

### Step C: Build engagement/window-level features
- File: `main/src/features/build_engagement_features.py`
- Entrypoint function: `main()`
- Key functions:
  - `first_visible_tick_los(...) -> int | None`
  - `first_shot_tick(...) -> int | None`
  - `build_for_zip(zip_path: Path) -> pl.DataFrame`
- Input path:
  - `ZIPS_DIR = C:\NullCS\parsed_zips`
  - reads from each zip: `ticks.parquet`, `kills.parquet`, `shots.parquet`
- Output path:
  - `OUT_ROOT = C:\NullCS\main\data\processed\demos`
  - per demo: `...\<demo_id>\engagement_features.parquet`
- Feature config constants:
  - `W_PRE=128`, `REQ_CONSEC=2`, `EYE_Z=64`, `CHEST_Z=56`, `MAX_DEMOS=None`, `OVERWRITE=True`
- Output columns generated in `rows.append(...)`:
  - `demo_id`, `map_name`, `round_num`, `kill_tick`, `t0_visible`, `first_shot_tick`, `rt_ticks`,
  - `attacker_steamid`, `attacker_name`, `victim_steamid`, `victim_name`, `weapon`, `headshot`, `distance`,
  - `visible_ticks_before_shot`, `visible_ticks_before_kill`,
  - `shots_last64_before_kill`, `shots_last128_before_kill`,
  - `is_micropeek_4`, `is_micropeek_6`, `is_micropeek_8`
- CLI args: none (hardcoded constants only)

### Step D: Aggregate kill/engagement rows to player-demo training table
- File: `main/src/features/aggregate_player_features.py`
- Entrypoint function: `main()`
- Key functions:
  - `load_cheater_map(csv_path: Path) -> dict[str, str]`
  - `demo_base_label(demo_id: str) -> int | None`
  - `safe_quantile(expr: pl.Expr, q: float) -> pl.Expr`
- Input paths:
  - `IN_ROOT = C:\NullCS\main\data\processed\demos`
  - reads: `*/engagement_features.parquet`
  - cheater labels: `CHEATER_CSV = C:\NullCS\main\data\processed\CheaterSteamIDs.csv`
- Label logic:
  - `Pro*` and `Normal*` demos => label `0`
  - `CDemo*` => per-player label from `CheaterSteamIDs.csv` exact SteamID match on `attacker_steamid`
- Output path:
  - `OUT_PATH = C:\NullCS\main\data\processed\player_features.parquet`
- Aggregated feature outputs include:
  - `n_kills_with_rt`, `rt_mean`, `rt_median`, `rt_p10`, `rt_p90`, `rt_std`, `fast_rt_rate`,
  - `headshot_rate`, `dist_mean`, `dist_median`, `dist_p90`, `weapon_n_unique`,
  - derived: `rt_iqr_80`, `dist_tail`
- Filtering config:
  - `MIN_KILLS=5`, `FAST_RT_TICKS=8`, `OVERWRITE=True`
- CLI args: none (hardcoded constants only)

### Step E: Train model (grouped CV grid search)
- File: `main/scripts/train_xgb_gridcv.py`
- Entrypoint function: `main()`
- Core API calls:
  - `GroupKFold(n_splits=5)`
  - `GridSearchCV(..., scoring='average_precision', cv=cv.split(X, y, groups=groups))`
  - `XGBClassifier(...)`
- Input path:
  - `DATA_PATH = C:\NullCS\main\data\processed\player_features.parquet`
- Grouping key (leakage control):
  - `groups = df['demo_id'].values`
- Feature selection logic:
  - excludes `{label, demo_id, map_name, attacker_name}`
  - numeric columns only
- Class imbalance handling:
  - `scale_pos_weight = n_neg / max(1, n_pos)`
  - passed into model and param grid
- Output directory and files:
  - `OUT_DIR = C:\NullCS\main\data\processed\models`
  - model: `xgb_player_level_gridcv.json`
  - feature list: `xgb_player_level_features.txt`
  - CV results: `xgb_gridcv_results.csv`
- CLI args: none

### Step F: Evaluate model + aggregate to demo-level suspicion
- File: `main/scripts/evaluate_xgb_gridcv.py`
- Entrypoint function: `main()`
- Core logic:
  - loads `player_features.parquet` and feature list from `xgb_player_level_features.txt`
  - computes OOF predictions with `GroupKFold(n_splits=5)` and `XGBClassifier(**BEST_PARAMS)`
  - metrics: `average_precision_score`, `roc_auc_score`, threshold confusion stats at `THRESHOLDS=[0.2,0.3,0.4,0.5]`
  - player ranking CSV output
  - demo aggregation by `max_proba`, `top1_mean`, `top3_mean`, `top5_mean`
- Input paths:
  - `DATA_PATH = C:\NullCS\main\data\processed\player_features.parquet`
  - `FEATS_PATH = C:\NullCS\main\data\processed\models\xgb_player_level_features.txt`
  - `MODEL_PATH` is defined but not loaded in this script
- Output directory/files:
  - `OUT_DIR = C:\NullCS\main\data\processed\reports`
  - `ranked_player_demo_suspicion.csv`
  - `ranked_demo_suspicion.csv`
- CLI args: none

### Step G (optional explainability report generation)
- Wrapper file: `main/scripts/explain_demo.py`
- CLI args (actual `argparse`):
  - `--demo` (required)
  - `--steamid` (optional)
  - `--name` (optional)
- Utility file: `main/src/utils/explain_demo.py`
- Key functions:
  - `default_config() -> ExplainConfig`
  - `_read_ranked(path)`
  - `pick_top_player_in_demo(cfg, demo_id, steamid=None, name=None)`
  - `load_engagement_features(cfg, demo_id)`
  - `build_reasons(top_row, eng)`
  - `explain_demo(cfg, demo_id, steamid=None, name=None)`
- Inputs:
  - ranked file: `main/data/processed/reports/ranked_player_demo_suspicion.csv`
  - engagement features: `main/data/processed/demos/<demo_id>/engagement_features.parquet`
- Outputs:
  - `main/data/processed/reports/<demo_id>/<steamid>/top_player_row.json`
  - `main/data/processed/reports/<demo_id>/<steamid>/reasons.json`
  - `main/data/processed/reports/<demo_id>/<steamid>/evidence_fast_rt.csv`

## 3) Exact Commands To Run

From repo root `C:\NullCS`:

1. Parse raw demos -> zipped parse bundles
```powershell
python main/src/parse/parse_demos_awpy_api.py
```

2. (Optional/alternate) Build canonical `events.parquet` from zipped parses
```powershell
python main/src/parse/build_events_from_zips.py
```

3. Build engagement/window features
```powershell
python main/src/features/build_engagement_features.py
```

4. Aggregate player-demo features + labels
```powershell
python main/src/features/aggregate_player_features.py
```

5. Train grouped-CV XGBoost with grid search
```powershell
python main/scripts/train_xgb_gridcv.py
```

6. Evaluate OOF + write ranked player/demo suspicion tables
```powershell
python main/scripts/evaluate_xgb_gridcv.py
```

7. Explain one demo/player (optional)
```powershell
python main/scripts/explain_demo.py --demo CDemo3
python main/scripts/explain_demo.py --demo CDemo3 --steamid 76561198762460140
python main/scripts/explain_demo.py --demo CDemo3 --name SomePlayerName
```

## 4) Known Gotchas (From Current Code)

1. `main/scripts/run_pipeline.py` references missing files.
- It calls:
  - `C:\NullCS\main\scripts\parse_demos_awpy_api.py`
  - `C:\NullCS\main\scripts\build_engagement_features.py`
- Those files do not exist under `main/scripts` in this workspace.
- Actual scripts exist under `main/src/parse/` and `main/src/features/`.

2. Path mismatch between events builder and main processed tree.
- `main/src/parse/build_events_from_zips.py` outputs to `C:\NullCS\processed\demos`.
- Aggregation/training pipeline reads from `C:\NullCS\main\data\processed\...`.
- If you rely on `build_events_from_zips.py`, it writes outside the `main/data/processed/demos` tree used later.

3. Class imbalance handling is active and data-dependent.
- Train/eval compute `scale_pos_weight = n_neg / max(1, n_pos)` from current labels.
- Any label distribution shift directly changes effective model weighting.

4. Group split is by `demo_id` (good), but there is no temporal split.
- `GroupKFold` avoids same-demo leakage across folds.
- It does not simulate future-vs-past chronological deployment.

5. Label quality depends on `CheaterSteamIDs.csv` completeness.
- For `CDemo*`, per-player labels come from exact SteamID match.
- Missing `CDemo` row => that entire demo is skipped by aggregator (`[WARN] ... Skipping this demo`).

6. Potential schema mismatch in explanation helper.
- `build_engagement_features.py` writes `t0_visible`.
- `main/src/utils/explain_demo.py` evidence column list expects `first_los_tick` (not produced by current feature builder), so that column is omitted from evidence output.

7. Evaluation script does not load saved model file.
- `MODEL_PATH` is defined in `evaluate_xgb_gridcv.py` but not used.
- Evaluation retrains fold models from hardcoded `BEST_PARAMS` and current feature file.

8. Overwrite defaults can silently replace artifacts.
- `build_engagement_features.py`: `OVERWRITE=True`
- `aggregate_player_features.py`: `OVERWRITE=True`

## 5) Minimal Verified Pipeline Order (Recommended)

1. `python main/src/parse/parse_demos_awpy_api.py`
2. `python main/src/features/build_engagement_features.py`
3. `python main/src/features/aggregate_player_features.py`
4. `python main/scripts/train_xgb_gridcv.py`
5. `python main/scripts/evaluate_xgb_gridcv.py`
6. `python main/scripts/explain_demo.py --demo <DemoID>`

This order matches the file paths and I/O expected by the current `main` training/evaluation scripts.

## 6) Smoke Test

Use this minimal end-to-end smoke test (evaluation -> explain report) from repo root:

```powershell
python main/scripts/evaluate_xgb_gridcv.py; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }; python main/scripts/explain_demo.py --demo CDemo3; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
```

Expected console output includes:
- `[INFO] loaded model from: C:\NullCS\main\data\processed\models\xgb_player_level_gridcv.json`
- `[OOF] PR-AUC=...  ROC-AUC=...`
- `[OK] wrote C:\NullCS\main\data\processed\reports\ranked_player_demo_suspicion.csv`
- `[OK] wrote C:\NullCS\main\data\processed\reports\ranked_demo_suspicion.csv`
- `=== DEMO REPORT: CDemo3 ===`
- `[OK] wrote: C:\NullCS\main\data\processed\reports\CDemo3\<steamid>`

Expected files updated/created:
- `main/data/processed/reports/ranked_player_demo_suspicion.csv`
- `main/data/processed/reports/ranked_demo_suspicion.csv`
- `main/data/processed/reports/CDemo3/<steamid>/top_player_row.json`
- `main/data/processed/reports/CDemo3/<steamid>/reasons.json`
- `main/data/processed/reports/CDemo3/<steamid>/evidence_fast_rt.csv`

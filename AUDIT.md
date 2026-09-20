# NullCS Research Pipeline Audit

Date: 2026-09-19
Scope: research pipeline only (`main/src`, `main/scripts`, data artifacts, environment). UI/product layers were inspected **only** to identify shared research dependencies.
Status: **Phase 0 audit complete. No existing file was modified.**

Method: `git` inspection, AST-based inventory of every module (entry points, CLI args, function sizes), symbol/reference grep across the repo, dependency-manifest comparison against the installed venv, and direct measurement of the current artifacts (row counts, file counts, load times). Everything below is either verified from code/artifacts or explicitly marked as unverified.

---

## 1. Git / safety snapshot (read this first)

| Item | Value |
| --- | --- |
| Branch | `chore/ui-evidence-only-2026-03-06` |
| HEAD | `c60219c Harden public beta experience` |
| Working tree | **dirty** (~50 modified/deleted UI+docs files, +10 research files) |

Research code that exists **only in the working tree** (untracked, i.e. not in any commit):

```
main/scripts/train_encounter_nn.py      main/scripts/infer_demo_from_path.py
main/scripts/ingest_pro_demos_cs2cd.py  main/scripts/score_benchmark_suite.py
main/scripts/score_encounter_nn.py      main/scripts/check_infer_determinism.py
main/scripts/analyze_cheater_misses.py  main/scripts/analyze_feature_separation.py
main/scripts/bootstrap_demo_ci.py       main/scripts/export_review_bundle.py
main/scripts/inspect_demo_report.py     main/scripts/run_pipeline.py
main/scripts/generate_*_plots.py        main/scripts/smoke_ui_pipeline.ps1
```

Research code heavily modified but uncommitted: `main/scripts/train_xgb_gridcv.py` (+255/-59), `main/scripts/evaluate_xgb_gridcv.py` (+417/-317), `main/scripts/run_infer_pipeline.py` (+82), `main/src/adapters/demoparser2_local.py` (+101), `main/scripts/calibrate_model.py`, `main/scripts/analyze_top1_misses.py`, `main/scripts/inspect_cs2cd_schema.py`, `main/scripts/generate_public_benchmark_plots.py`, `main/ui/api/requirements*.txt`.

> **RISK-0 (critical):** the current neural-net + CS2CD pipeline has never been committed. A `git checkout .` / `git clean -fd` / worktree switch would destroy it. The first action of any refactor phase must be a checkpoint commit of the research tree (excluding `main/data/**`, which is already gitignored).

Trees that must be **excluded** from every search/refactor (duplicate copies of this repo): `.worktree-main/`, `.push-main/`, `.merge_main/`, `main/ui/web/src-tauri/target/release/resources/nullcs-backend/` (ships a full copy of `main/src` and `main/scripts`), `NewAnubisTri/.venv/`, `main/ui/site/**`.

---

## 2. Source of truth: the actual pipeline

There are **two data branches** feeding one shared model layer. Branch A is the default and produces the published numbers; Branch B is the original pipeline, still fully wired but legacy.

### Branch A - CS2CD (ACTIVE, default `NULLCS_TRAIN_DATA=cs2cd`)

```
huggfacedata/<split>/<match_id>.{parquet,json}      1590 matches, 50.2 GB, 1592 files
  -> src/adapters/cs2cd_adapter.py :: load_match()  (already-parsed tables; no .dem parsing)
  -> src/features/build_cs2cd_engagement_features.py :: process_split()
        -> main/data/processed/demos/<demo_id>/{engagement_features.parquet, encounters.parquet, meta.json}
  -> scripts/train_encounter_nn.py                   (temporal CNN, OOF)
        -> main/data/processed/encounter_nn_cs2cd_temporal_seq32.npz            (624 MB cache)
        -> main/data/processed/models/encounter_nn_cs2cd.pt + _preproc.pkl + _features.json
        -> main/data/processed/encounter_nn_cs2cd_player_features.parquet       (NN -> player aggregates)
  -> src/features/aggregate_player_features.py       (~450 features per player-demo)
        -> main/data/processed/player_features_cs2cd.parquet
  -> scripts/train_xgb_gridcv.py                     (GroupKFold grid search)
        -> models/xgb_player_level_cs2cd.json + _features.txt + _best_params.json + _gridcv_results.csv
  -> scripts/evaluate_xgb_gridcv.py                  (OOF fold retraining + ranking reports)
        -> reports/ranked_player_demo_suspicion_oof_cs2cd.csv
        -> reports/ranked_demo_suspicion_oof_cs2cd.csv, top1_misses_cs2cd.csv
  -> optional: calibrate_model.py, analyze_feature_separation.py, analyze_cheater_misses.py,
               bootstrap_demo_ci.py, explain_demo.py
```

Separate ingestion path for local pro demos (raw `.dem` -> CS2CD-style table): `scripts/ingest_pro_demos_cs2cd.py` (uses `src/adapters/demoparser2_local.py`) -> `CS2CD_PROLEGIT_*` demo dirs, labelled by `meta.json.source_demo`; consumed by the same feature/aggregation chain.

### Branch B - local_awpy (LEGACY, `--train-data local`)

```
CheaterDemos/, LegitDemos/{NormalRenamed,ProsRenamed}/   *.dem, 76 GB, 245 files
  -> src/parse/parse_demos_awpy_api.py (awpy 2.0.2) -> parsed_zips/<stem>.zip   (253 zips, 1.64 GB)
  -> src/features/build_engagement_features.py       (awpy; near-duplicate of the CS2CD builder)
  -> src/features/aggregate_player_features.py --train-data local
        -> main/data/processed/player_features.parquet                          (1.3 MB, Feb 2026)
  -> src/parse/build_events_from_zips.py -> C:\NullCS\processed\demos             ** ORPHANED **
```

`build_events_from_zips.py` has **zero references anywhere** in `main/`, and its output root (`C:\NullCS\processed\demos`) has **zero consumers**. It is dead code on a dead branch.

### Inference path (shared by UI + CLI) - this is where duplication lives

```
scripts/run_infer_pipeline.py :: main()            <-- CANONICAL (reuses the training aggregator)
   -> _build_player_features_for_demo() -> agg_mod.aggregate_kill_and_encounter_frames()   [shared]
   -> _merge_encounter_nn_features_for_demo() -> encounter_nn.aggregate_encounter_scores()
   -> _infer_scores(): resolve_model_artifacts + model feature list + calibrator + scoring.risk_*
scripts/infer_demo_from_path.py :: aggregate_single_demo_features()   <-- DUPLICATE aggregator
   -> agg_mod.build_row() + a hand-copied block of derived-feature math (~122 lines)
scripts/score_benchmark_suite.py    -> invokes run_infer_pipeline per demo (good)
scripts/check_infer_determinism.py  -> hashes inference outputs (good, keep)
main/ui/api/main.py                 -> run_infer_pipeline, resolve_model_artifacts,
                                        behavioral_context, utils.explain_demo, training_mode
```

Consumers of research modules that must not have their interfaces broken: `main/ui/api/main.py` (desktop/API), `main/ui/api/tests/test_security.py`.

---

## 3. Component inventory (research only)

| Path | Role | Used by | Status |
| --- | --- | --- | --- |
| `src/adapters/cs2cd_adapter.py` | CS2CD match loader | build_cs2cd, encounter_nn | active |
| `src/adapters/demoparser2_local.py` | `.dem` -> tables (demoparser2) | ingest_pro, encounter_nn, run_infer | active |
| `src/features/build_cs2cd_engagement_features.py` | encounters + engagement rows | pipeline A | active |
| `src/features/build_engagement_features.py` | same, awpy/zips | `--train-data local` only | legacy |
| `src/features/aggregate_player_features.py` | ~450 player-demo features | A + B + inference | active |
| `src/models/encounter_nn.py` | preprocessors + CNN + temporal tensors + scoring | train/score/infer | active |
| `src/utils/{project_paths,training_mode,demo_labels,scoring,model_registry}.py` | config/labels/scoring | many | active |
| `src/utils/behavioral_context.py` (650 L) | explanation text/archetypes | UI + explain_demo | active |
| `src/utils/{explain_demo,bootstrap_demo_ci}.py` | per-demo evidence | CLI + UI | active |
| `src/utils/{visibility_awpy,awpy_map_assets,los_sanity_test,visibility_quickcheck}.py` | LOS tooling | sanity checks only | low-use |
| `src/utils/{parquet_to_samplecsv,print_zip_columns}.py` | ad-hoc inspection | manual | low-use |
| `src/parse/{parse_demos_awpy_api,build_events_from_zips}.py` | zip parsing | B / none | legacy / orphan |
| `scripts/train_encounter_nn.py`, `score_encounter_nn.py` | NN train/score | pipeline A | active |
| `scripts/train_xgb_gridcv.py`, `evaluate_xgb_gridcv.py`, `calibrate_model.py` | GBM train/eval | pipeline A | active |
| `scripts/run_infer_pipeline.py` | inference entry | UI, suite | active |
| `scripts/infer_demo_from_path.py` | older inference CLI | manual | duplicate |
| `scripts/score_benchmark_suite.py`, `check_infer_determinism.py` | benchmarks/repro | manual | active |
| `scripts/analyze_{feature_separation,cheater_misses,top1_misses}.py` | analysis | manual | active |
| `scripts/generate_*plots*.py` (4 files) | plots (`docs/assets`) | publishing | reporting |
| `scripts/export_review_bundle.py`, `inspect_demo_report.py`, `ingest_pro_demos_cs2cd.py` | tooling | manual | active |
| `scripts/inspect_cs2cd_schema.py` | dataset audit | one-off | keep as doc-gen |

Root-level `engagement_features.py`, `parse_demo.py`, `run_batch.py`, `preaim_through_wall.py`, `LegitvsBlatantCurves.py`, `extract_and_rename_pro_demos.py`, `nullcs.py`, and the `Tick Level/`, `Post 100 Scripts New/`, `Plots/`, `model/`, `cheat_training/`, `raw_parsed/`, `outputs/`, `tris/`, `legit_baseline_outputs/`, `NewAnubisTri/` (except `.venv`) trees appear to be historical experiments. **Not deleted, not assumed dead** - see section 6 decision point D1.

---

## 4. Measured baseline (before refactor)

| Measurement | Value |
| --- | --- |
| CS2CD input | 1590 matches / 50.2 GB (`no_cheater_present` 956, `with_cheater_present` 634) |
| `encounters.parquet` | 1410 files, 405,065 rows, 257 MB; **metadata-only scan of all files = 8.9 s** |
| `engagement_features.parquet` | 1642 files, 225,378 rows |
| Temporal cache `.npz` | 624.6 MB on disk; 281,792 x 35 x 32 float32 = **1.26 GB in RAM; load+decompress 4.32 s** |
| Temporal cache manifest JSON | **15.35 MB** (stores every `demo_id` + `attacker_steamid`) |
| `player_features_cs2cd.parquet` | 6,973 rows x 469 cols, 15.3 MB, read **0.22 s** |
| 449-feature model list | all 449 present in the parquet; only 20 non-feature columns exist |
| Player table (pre-filter) | 882 demos, 1052 positives, 5921 negatives |
| `main/data/processed/demos` | **1661 dirs / 5049 files / 435.8 MB** (only ~894 CS2CD + 220 legacy are training inputs) |
| `main/data/processed/reports` | **566 dirs**, incl. 8 experiment variants x ~48 MB ranked CSVs (~380 MB) |
| `main/data/raw_uploads` | **187.5 GB / 622 `.dem` files** for ~40 distinct demos (repeated copies) |
| `parsed_zips` / `CheaterDemos` / `LegitDemos` / `tris` | 1.64 GB / 10.8 GB / 65.3 GB / 475 MB |
| Python | 3.13.5 (`NewAnubisTri/.venv`; identical to system `C:\Python313`) |
| torch | 2.11.0 **CPU-only wheel - no `nvidia-*` packages installed**, so `--device cuda` is inert |

---

## 5. Findings

Severity: **S1** = correctness/reproducibility risk, **S2** = performance/duplication, **S3** = hygiene.

| # | Sev | Finding | Evidence |
| --- | --- | --- | --- |
| F1 | S1 | Active research pipeline is uncommitted (untracked + heavily modified files). | section 1 |
| F2 | S1 | Default inference model is chosen by `mtime` "newest wins", so it currently resolves to `xgb_player_level_cs2cd_ranksel_child5.json` (an experiment, Apr 2026), while the **documented** eval artifacts belong to stem `xgb_player_level_cs2cd` (Aug 2026). Model used != model documented. | `src/utils/model_registry.py::_candidate_models`; `models/` listing |
| F3 | S1 | Feature selection is *locked* only when `--feature-list-path` is passed. Without it, `train_xgb_gridcv.py` auto-selects every numeric column except 6 identifiers - which silently **adds 14 lobby-normalised/style columns** (`*_pct`, `*_z`, `*_style_score`, `*_gap`) and changes the 449-feature contract. | `train_xgb_gridcv.py` `exclude={...}`; 469-449=20 columns |
| F4 | S1 | Two independent implementations of player-demo aggregation: `aggregate_player_features.aggregate_kill_and_encounter_frames()` (canonical) and `infer_demo_from_path.aggregate_single_demo_features()` (~122 lines of copied derived-feature math: `laplace` rates, weapon splits, `*_w`, `rt_iqr_80`, `dist_tail`, `*_shrunk`). Drift here means **inference features stop matching training features**. `run_infer_pipeline.py` correctly delegates and is the model to copy. | AST + code read |
| F5 | S1 | `src/parse/build_events_from_zips.py` is orphaned and writes to `C:\NullCS\processed\demos`, which nothing reads. | zero references anywhere in `main/` |
| F6 | S2 | Temporal-sequence build re-loads the whole match per demo: `build_temporal_sequences_for_demo()` -> `_load_match_for_demo_id()` re-reads the full ticks parquet + events JSON and rebuilds indexes. For CS2CD that is a **second full read of every match** after the feature build; for `TEST_`/`BENCH_`/PROLEGIT ids it re-parses the `.dem` with demoparser2. Called per demo, and again inside `score_encounter_frame()` during inference. | `src/models/encounter_nn.py` L346/L420/L687 |
| F7 | S2 | `build_temporal_sequences_for_demo()` is a per-encounter Python loop (`itertuples` + ~40 `pd.to_numeric/.get().fillna()` calls per row) over 281,792 encounters; `_event_distances` recomputes sorted event sets per row. Strong vectorisation candidate inside the same per-demo grouping. | `encounter_nn.py` L420-583 |
| F8 | S2 | Cache validation parses a **15.35 MB JSON manifest** (all demo_ids + steamids) on every training run before touching the 624 MB npz. | `train_encounter_nn.py::_load_temporal_cache` |
| F9 | S2 | Near-duplicate feature builders: `build_engagement_features.py` (awpy, 960 L) vs `build_cs2cd_engagement_features.py` (977 L) share `wrap_deg`, `aim_error_deg`, `build_pair_tick_table`, `enrich_pair_ticks`, `first_shot_tick`, `_quantile/_mean/_std`. Only the tick source differs. | AST duplicate-name scan (30 duplicate names total) |
| F10 | S2 | Label/helper duplication: `load_cheater_map`, `demo_base_label`, `label_demo_frame_pl`, `ensure_columns_pl`, `_split_steamids` exist in **both** `src/utils/demo_labels.py` and `src/features/aggregate_player_features.py`. | AST |
| F11 | S2 | `build_sample_weights` is duplicated in train/eval. Verified: semantics identical, representation differs (`Series` always vs `ndarray`/`None`). Safe to consolidate. | diff of both functions |
| F12 | S2 | `n_players>=8` filtering, `scale_pos_weight`, threshold sweeps and demo-level aggregation are re-implemented across `train_xgb_gridcv`, `evaluate_xgb_gridcv`, `analyze_*`, `calibrate_model` - repeated data-prep on the same table. | code read |
| F13 | S2 | Every evaluation run retrains 5 fold models and writes ~48 MB ranked CSVs + ~47 MB OOF CSVs; 8 experiment variants are already on disk (~380 MB) with no consumers except manual comparison. | `reports/` listing |
| F14 | S2 | `main/data/processed/demos` holds 1661 dirs (5049 files) but only ~894 CS2CD + 220 legacy are training inputs; UI smoke tests (`TEST_*`, `WEB_*`, `BENCH_*`) inflate every glob and metadata scan (8.9 s for one glob+scan). | measured |
| F15 | S2 | `main/data/raw_uploads` = 187.5 GB / 622 `.dem` copies (~40 unique demos). Pure waste; also makes any recursive scan/diff slow. | measured |
| F16 | S2 | DataLoader in NN training uses `num_workers=0`, no `pin_memory`, no `persistent_workers`; tensors are pre-materialised in RAM so gains are limited, but `pin_memory`/workers are free wins if CUDA is ever enabled. | `train_encounter_nn.py::_make_loader` |
| F17 | S3 | `--device cuda` is accepted everywhere but the installed torch is CPU-only; no `torch.amp/autocast` usage anywhere. Mixed precision is not currently testable. | pip list; grep |
| F18 | S3 | No research tests, no `pytest.ini`/`conftest.py`; the only test file is `main/ui/api/tests/test_security.py` (a root `.pytest_cache` exists). | filesystem scan |
| F19 | S3 | Three copies of parquet->CSV tooling: `src/utils/parquet_to_samplecsv.py`, `Tick Level/parquet_to_sample_csv.py`, `Post 100 Scripts New/parquet_to_sample_csv.py`. | filesystem |
| F20 | S3 | Undeclared direct imports: `joblib` (`src/utils/scoring.py`, `scripts/calibrate_model.py`) and `matplotlib` (4 plot scripts) are not in `requirements.txt` (joblib only arrives transitively via scikit-learn). | grep vs requirements |
| F21 | S3 | Installed but unused by `main/src`+`main/scripts`: `datasets`, `huggingface_hub`, `tqdm`, plus desktop-packaging transitives (`pyinstaller`, `pefile`, `win32_setctime`, `inquirerpy`, `loguru`). | grep (0 hits) |
| F22 | S3 | `awpy` is now used only by the legacy zip path and LOS utilities; the active CS2CD path uses `demoparser2`. | grep (3 files) |
| F23 | S3 | Docs drift: `PIPELINE.md` "Core Commands" lists only the legacy awpy sequence; `README.md`/`METHODOLOGY.md`/`RESULTS.md` describe the CS2CD + CNN pipeline. `AGENTS.md` is stale (claims `main/src/models` is empty, documents the pre-CS2CD flow, and its `first_los_tick` gotcha no longer applies - the symbol appears nowhere). | docs read + grep |
| F24 | S3 | No orchestrator for the active pipeline: `run_pipeline.py` runs only the legacy awpy chain; the CS2CD chain (ingest -> features -> NN -> aggregate -> train -> eval) has no single entry point. | `run_pipeline.py` |
| F25 | S3 | Hardcoded absolute paths remain in 3 trailer/plot scripts (`C:\...`). Reporting only, no research impact. | grep |
| F26 | S3 | Dependency manifest (`main/ui/api/requirements.txt`) mixes research + UI deps and lives under the UI tree; there is no top-level research requirements file. | file read |

**Explicitly checked and NOT problems** (to prevent wasted work):

* `*_pct` / `*_z` columns are computed **per lobby** (`add_demo_norms` groups by `demo_id`), so they are not cross-dataset leakage and are reproducible for a single inferred demo.
* All 449 model features exist in `player_features_cs2cd.parquet`; the aggregator currently in the repo reproduces the column set of the trained table.
* `run_infer_pipeline._build_player_features_for_demo` already delegates to the canonical aggregator.
* `git`-tracked `main/src/features/*` and `main/scripts/train_encounter_nn.py` are unchanged vs HEAD, so the CS2CD feature/NN code that produced the current artifacts is exactly what is on disk.

---

## 6. Proposed plan (for approval - nothing executed yet)

Ordering is deliberate: protect first, then measure, then change the cheapest things that cannot alter research semantics.

| Phase | Work | Risk | Expected gain |
| --- | --- | --- | --- |
| 1a | **Checkpoint commit** of the research tree (untracked + modified research files only, `main/data/**` stays ignored). | none | eliminates RISK-0 |
| 1b | Freeze a baseline: record `player_features_cs2cd.parquet` and `ranked_*_oof_cs2cd.csv` hashes/statistics, plus run `check_infer_determinism.py` on one demo. | none | gives the comparison target |
| 1c | **Model-artifact ambiguity fix**: make inference default to an explicit, documented artifact (`xgb_player_level_cs2cd`) instead of "newest mtime", or pass `--model-artifact` explicitly everywhere. Decide with owner. | low, changes which model inference uses | removes F2 |
| 2a | Consolidate duplicated helpers with **identical semantics only**: `demo_labels` helpers (F10), `build_sample_weights` (F11), `_load_local_module` (F10/F11). | low | -150 LOC, one source of truth |
| 2b | Delete/retire the **orphan** `build_events_from_zips.py` + `processed/demos` branch (or keep and mark deprecated). | low | removes a dead pipeline branch |
| 2c | Add explicit `--feature-list-path` default to training/eval so the 449-feature contract cannot silently change (F3). | low | removes methodology-drift hazard |
| 3a | Inference: make `infer_demo_from_path.py` call the canonical aggregator (`aggregate_kill_and_encounter_frames`) instead of its copied math; verify byte-level feature equality on a `TEST_` demo (F4). | medium - needs numeric equality check | removes the largest correctness hazard |
| 3b | Cache match tables per demo inside the temporal-sequence build (single load reused for tick index + sequences); optional on-disk cache keyed by `demo_id` (F6). | medium | removes 1 full re-read of every match; biggest CPU/IO win on NN rebuilds |
| 3c | Vectorise the per-encounter loop in `build_temporal_sequences_for_demo` in place (no change to channel math), validated by exact array comparison against the current cache (F7). | medium | large speed-up on cache rebuilds |
| 3d | Dataset hygiene: list/verify/archive `TEST_*`, `WEB_*`, `BENCH_*` demo dirs and dedupe `raw_uploads` (F14/F15). Requires owner confirmation before deleting anything. | medium | 187 GB + faster globs |
| 4a | Orchestrator for the canonical CS2CD chain (`scripts/run_research_pipeline.py`), env-var driven, no hardcoded paths (F24). | low | reproducibility |
| 4b | Minimal smoke tests: feature-count/order contract, aggregation parity (training vs inference), OOF determinism, cache-invalidation logic (F18). | low | regression safety net |
| 4c | Dependencies: add `joblib` + `matplotlib` (research/reporting) explicitly; split UI-only and packaging-only deps; document torch CPU-only reality (F17/F20/F21/F26). No version bumps without an A/B output comparison. | low | honest environment |
| 5 | Docs: rewrite `PIPELINE.md` around the CS2CD+CNN chain, update `AGENTS.md` to the real tree, keep README/METHODOLOGY/RESULTS as-is (they already match the artifacts). | none | F23 |

Explicitly **out of scope**: changing labels, tick windows, encounter definitions, feature math, normalisation, missing-value policy, aggregation semantics, CV methodology, or model architecture.

## 7. Decision points needing an owner call

* **D1** - Root-level experimental trees (`Tick Level/`, `Post 100 Scripts New/`, `model/`, `cheat_training/`, `raw_parsed/`, `Plots/`, root `*.py`): archive to `.legacy/` (move, not delete), delete after confirmation, or leave untouched?
* **D2** - Which artifact is the intended production/reporting model: `xgb_player_level_cs2cd` (matches README/RESULTS) or `xgb_player_level_cs2cd_ranksel_child5` (what inference picks today)?
* **D3** - Is `--train-data local` (awpy branch) still required for research, or is CS2CD the only branch that must keep working? This decides whether `build_engagement_features.py` is consolidated with the CS2CD builder or merely frozen.
* **D4** - May I delete `TEST_*`/`WEB_*`/`BENCH_*` demo dirs, `raw_uploads` duplicates, and the superseded `*_prune_*/_support_*/_reduce_*` report variants (after listing them for review)?
* **D5** - Is GPU training ever going to be used? If not, the `--device cuda` plumbing stays but the environment should be documented as CPU-only.

---

## 8. Phase 1 execution log (2026-09-19)

### Decisions recorded

| ID | Answer | Verification performed |
| --- | --- | --- |
| D2 | Canonical model = `xgb_player_level_cs2cd`. The mtime-based "newest model" default is to be fixed. | **Confirmed live:** every inference run today logged `[INFO] selected model: xgb_player_level_cs2cd_ranksel_child5.json train_mode=cs2cd`. |
| D3 | awpy retired; only CS2CD matters. Keep awpy code because it is still imported somewhere. | Verified the live path is awpy-free: `awpy` appears only in `scripts/infer_demo_from_path.py`, `src/parse/parse_demos_awpy_api.py`, `src/utils/visibility_awpy.py`, `src/features/build_engagement_features.py` (legacy), `src/utils/visibility_quickcheck.py`. Nothing in `run_infer_pipeline.py`, `encounter_nn.py`, `cs2cd_adapter.py`, `demoparser2_local.py`, `build_cs2cd_engagement_features.py` or `aggregate_player_features.py`. Nothing deleted - removal deferred to 2b/3. |
| D4 | Yes - remove temp inference / CV-testing artifacts. | Executed with content-signature proof, see below. |
| D5 | CUDA for training later (16 GB 5060 Ti); inference stays CPU-only. | Environment today: venv has `torch 2.11.0+cpu`, `torch.cuda.is_available() == False`. Keep `--device cuda` plumbing, document CPU-only reality. |
| D1 | Not yet answered. Root-level experimental trees untouched. | - |

### 1a - Checkpoint commit: DONE

`4a36809` "research: checkpoint CS2CD + CNN pipeline before Phase 0 refactor" - 32 files (19 previously-untracked scripts, 8 modified research files, 4 docs incl. previously-untracked `PIPELINE.md`/`METHODOLOGY.md`/`RESULTS.md`/`AGENTS.md`, `AUDIT.md`, 2 dependency manifests).
Excluded on purpose: UI/site/web edits, media assets, `.worktree-main/`/`.push-main/`/`.merge_main/` copies. `main/data/**` stays gitignored.
`git status` for `main/src`, `main/scripts`, docs and manifests is now empty - RISK-0 closed.

### 1b - Baseline freeze: DONE

End-to-end validation on `CheaterDemos/Demo6.dem` (142 MB, smallest cheater demo) with a supported id:

```
python main/scripts/run_infer_pipeline.py --dem_path C:\NullCS\CheaterDemos\Demo6.dem \
       --demo_id TEST_20260919_audit_smoke --out_dir C:\NullCS\main\data\processed     -> exit 0
```

wrote `engagement_features.parquet`, `encounters.parquet`, `encounter_nn_player_features.parquet`,
`player_features_infer.parquet`, `ranked_players_infer.csv`, `debug_score_trace.json`, `infer_manifest.json`.

Determinism baseline (two independent runs, `COMPARE` of `debug_score_trace.json`):

* 4 players, identical player-id sets
* model sha256 identical: `527dc49aea109487b34bd58807fa36b8a854babb0c970a42329853464c0acf68`
* max |raw_proba difference| = `0.000e+00` (**bit-identical**)
* model actually loaded: `xgb_player_level_cs2cd_ranksel_child5.json` (F2 confirmed on the live path)

All validation artifacts were removed afterwards; demo dirs returned to 1239.

### 3d - Dataset hygiene: DONE (measured)

| Tree | Before | After | Reclaimed | Rule |
| --- | --- | --- | --- | --- |
| `main/data/raw_uploads` | 622 files / 196.56 GB | 15 files / 4.26 GB | **192.30 GB** | delete only files whose content signature (size + blake2b of first 4 MB) matched a `.dem` still present in `CheaterDemos`/`LegitDemos` (556 files), plus intra-`raw_uploads` duplicates keeping exactly one copy (51 files); kept 11 files that are the only copy of their content, plus 4 explicit keeps |
| `main/data/processed/demos` | 1661 dirs / 0.46 GB | 1239 dirs / 0.26 GB | 422 dirs / 194.9 MB | temp-prefix caches: `RANKSEL_` 316, `TEST_` 93, `SMOKE_` 5, `WEB_` 3, `STYLECHK_` 3, `DET_` 2 |
| `main/data/processed/reports` | 566 dirs / 1.50 GB | 473 dirs / 0.81 GB | 28 CSVs (667 MB) + 93 orphaned timestamped temp dirs (17.2 MB) | superseded `_prune_*/_support_*/_reduce_*` CV variant CSVs; timestamped temp report dirs with no matching demo dir |

Total reclaimed: **~193.2 GB**.

No delete was performed without proof of redundancy: the removed raw demos are byte-identical to `.dem`
files that still exist in `CheaterDemos`/`LegitDemos`, and the removed demo caches are regenerable because
the benchmark ids are deterministic (`BENCH_{BUCKET}_{stem}`, `RANKSEL_{VARIANT}_{BUCKET}_{stem}`).

### Deliberately preserved (functionality > cleanliness)

* `BENCH_*` processed demo dirs (120) - read by `generate_site_control_proof_plots.py` (`player_features_infer.parquet`), i.e. the published control-path proof plots. Deleting them would have required a 120-demo re-run first.
* `CLI_SMOKE_BENCH_CHEATER_Demo1`, `README_PERF_20260503_122036`, `TEST_20260403_164759_d8269f6a`, `TEST_20260407_130853_1f420890` (+ their raw copies) - `generate_real_trailer_graphs.py` reads the two trailer demos; the CLI/README runs back published perf/README numbers.
* `reports/encounter_nn_cs2cd_oof_encounters.csv` (357 MB) - referenced by `RESULTS.md` and by the NN trainer/scorer code.
* Canonical artifacts re-verified present after cleanup: `models/xgb_player_level_cs2cd.json` + `_features.txt`, `models/encounter_nn_cs2cd.{pt,preproc.pkl,features.json}`, `player_features_cs2cd.parquet`, `encounter_nn_cs2cd_temporal_seq32.npz` (624 MB), `encounter_nn_cs2cd_player_features.parquet`, `ranked_player_demo_suspicion_oof_cs2cd.csv`, `ranked_demo_suspicion_oof_cs2cd.csv`, `top1_misses_cs2cd.csv`, `player_oof_predictions_cs2cd.csv`, `ranked_player_demo_suspicion_infer.csv`.

### New findings discovered during Phase 1

| # | Sev | Finding | Evidence |
| --- | --- | --- | --- |
| F27 | S1 | **`check_infer_determinism.py` can never pass.** It generates `DET_*` ids, but `encounter_nn._load_match_for_demo_id` supports only `CS2CD_*`, `CS2CD_PROLEGIT_*`, `TEST_*`, `BENCH_*` (plus `meta.json`-backed ids). The NN scoring is therefore skipped and `run_infer_pipeline._validate_inference_feature_frame` raises `RuntimeError: Model expects encounter neural-network features, but none were produced. Refusing to zero-fill stacked model signals.` (exit 1). Net effect: **the repo has no working determinism guard**; the baseline in 1b had to be produced manually with a `TEST_` id. Also proves the stacked model hard-requires encounter-NN features: any unsupported demo id can never be scored. | two captured runs, exit 1, full traceback |
| F28 | S2/S3 | **The workspace path is an alias:** `C:\NullCS` is a directory **junction** to the real root `C:\ClarityCS` (`Get-Item` LinkType=Junction/Target=C:\ClarityCS; identical `fsutil file queryfileid`; `git -C C:\ClarityCS log` shows the same commits). `project_paths.find_repo_root` canonicalises through `Path.resolve()`, so `REPO_ROOT`/`PROCESSED_ROOT` always resolve to `C:\ClarityCS\...` even when invoked from `C:\NullCS`. This is **not** a split data tree - it is one live tree, so all audit measurements and the D4 cleanup apply to the live data. Side effects: (a) log lines print `C:\ClarityCS\...`; (b) the hardcoded `C:\ClarityCS\...` paths (F25) are the canonical root - they work here but break on any move/clone/CI checkout; (c) the pipeline mirrors uploads into `main/data/raw_uploads/<demo_id>/<demo_id>.dem`, which is how the 622-file duplication arose. | junction attributes, file IDs, traceback paths |
| F29 | S3 | **UI job history is now partly dangling.** `main/ui/api/state/jobs.json` (untracked local UI state) holds 67 `TEST_*` entries whose processed demo dirs were removed by the D4 cleanup; only the 2 published-trailer `TEST_` demo dirs survive. Remedy if it matters: clear/repoint the in-app history, or re-run inference for those demos (ids are regenerable from `CheaterDemos`/`LegitDemos`). | grep of `jobs.json` + post-cleanup dir counts |
| F30 | S3 | **330 orphaned per-demo evidence dirs remain under `reports/`** for the superseded rank-selection experiments (`RANKSEL_*_CHEATER_Demo*`, `RANKSEL_*_NORMAL_*`, `RANKSEL_*_PRO_*`, `SMOKE_*`, `STYLECHK_*`, `WEB_*`, `DET_20260227_*`, `TEST_20260227_SCOREAUDIT`). Their demo dirs are gone, so they cannot be re-derived without re-inference. Kept deliberately as the "list for review" remainder of D4 - they are small, but they are dead weight and a source of confusion when globbing `reports/`. | `reports/` listing |

### Updated baseline (post-cleanup)

| Measurement | Value |
| --- | --- |
| `raw_uploads` | 15 files / 4.26 GB (was 622 / 196.56 GB) |
| `processed/demos` | 1239 dirs / 3784 files / 0.26 GB (was 1661 / 5049 / 0.46 GB) |
| `processed/demos` composition | `CS2CD_` 895, `BENCH_` 120, `Normal*` 100, `Pro*` 100, `CDemo*` 20, `CLI_` 1, `README_` 1, `TEST_` 2 |
| `processed/reports` | 473 dirs / 1490 files / 0.81 GB (was 566 / 2131 / 1.50 GB) |
| `processed/models` | 39 files / 0.02 GB |
| Canonical data artifacts | all present (verified individually) |
| Live inference | exit 0 on `CheaterDemos/Demo6.dem`; bit-identical across two runs |
| Model loaded by inference | `xgb_player_level_cs2cd_ranksel_child5.json` (contradicts D2, fix pending in 1c) |

### Plan status after Phase 1

| Phase | Status |
| --- | --- |
| 1a checkpoint commit | **done** (`4a36809`) |
| 1b baseline freeze | **done** (determinism bit-identical, artifacts verified) |
| 1c pin/lock the inference model artifact (F2) | **done** - canonical `xgb_player_level_cs2cd` pinned, evidence in section 9 |
| 2a dedupe identical helpers (F10/F11), 2b retire orphan `build_events_from_zips.py` (F5), 2c lock the 449-feature contract (F3) | **done** - evidence in section 10 |
| 3a inference/serving aggregation parity (F4) | **done** - evidence in section 10 |
| 3b match-load caching (F6), 3c vectorise temporal build (F7) | pending |
| 3d dataset hygiene | **done** (~193.2 GB reclaimed) |
| 4a CS2CD orchestrator, 4b smoke tests + **fix the determinism guard (F27)**, 4c dependency honesty (F17/F20/F21/F26) | pending |
| 5 docs rewrite (`PIPELINE.md`, `AGENTS.md`) | pending |

1c is complete (section 9): `xgb_player_level_cs2cd` is pinned as the inference artifact. Awaiting a go/no-go only for **F30** (delete the 330 orphaned rank-selection report dirs) and for promoting the `ranksel_depth4` lead described in section 9.6.

---

## 9. Phase 1c - inference model pin: evidence and artifact comparison (2026-09-19)

Owner decision on D2 confirmed: keep **`xgb_player_level_cs2cd`**. The artifact mtime selection had been loading (`xgb_player_level_cs2cd_ranksel_child5`) is an unvalidated, uncalibrated experiment and is **not** better on any controlled metric.

### 9.1 The fix (F2 closed)

`src/utils/model_registry.py::resolve_model_artifacts` now resolves in this order:

1. explicit `model_artifact=` argument - every CLI flag (`--model-artifact`) and env var (`NULLCS_MODEL_ARTIFACT`, `CLARITY_MODEL_ARTIFACT`) still wins;
2. the pinned canonical artifact `xgb_player_level_cs2cd.json` (`DEFAULT_MODEL_STEM`);
3. legacy newest-mtime `xgb_*.json` selection **only if** the canonical file is missing (so a renamed artifact cannot hard-fail inference).

`NULLCS_DEFAULT_MODEL_STEM` / `CLARITY_DEFAULT_MODEL_STEM` can repoint the pin for experiments without a code edit. Verified resolution matrix: default -> `xgb_player_level_cs2cd.json`; explicit `..._ranksel_child5.json` -> still selectable; explicit `xgb_player_level_gridcv.json` -> unchanged; env override honoured; canonical-absent -> newest-mtime fallback; empty dir -> `FileNotFoundError`.

Acceptance test (same invocation as the 1b baseline, `CheaterDemos/Demo6.dem`):

| Evidence | Before (1b) | After |
| --- | --- | --- |
| Log line | `selected model: xgb_player_level_cs2cd_ranksel_child5.json` | `selected model: xgb_player_level_cs2cd.json train_mode=cs2cd` |
| Exit code | 0 | 0 |
| `infer_manifest.json` model sha256 | `527dc49aea109487...` | `f9016d95a144e1004f40c01f15b86879d9d9101cdda4659acaa261ac80610ea8` |
| Calibration | `proba_calibrated` empty, `risk` = raw | `proba_cheater_infer 0.9609` -> `proba_calibrated = risk = 0.8164`, `risk_band=high_priority` |

All smoke artifacts were removed afterwards: `processed/demos` back to 1239 dirs, `raw_uploads` 15 files, `processed/models` 39 files, and `xgb_player_level_cs2cd_eval_summary.json` byte-restored (`0DB855F0A6CFF205E65AA79328C09113E5D213DB470103E00F3E5F96EFBC3D69`).

### 9.2 What the four `*_cs2cd*` artifacts actually are

All four share a **byte-identical 449-feature contract** (`xgb_player_level_cs2cd_features.txt`; raw sha `26dfc6461569...` = CRLF, normalised `2ec454a76460...` = the value stored in the training manifests, so the two hashes seen in the wild are the same file). Differences are hyperparameters only:

| Artifact | Bytes | sha256 (16) | Rounds | max_depth | min_child_weight | Trained | Calibrator | 40-demo cheater slice |
| --- | ---: | --- | ---: | ---: | ---: | --- | --- | --- |
| `xgb_player_level_cs2cd.json` (pinned) | 948,824 | `f9016d95a144e100` | 800 | 3 | 8 | 2026-03-29 15:03 | **yes** | top1 0.600 / top3 0.900 |
| `..._ranksel_base.json` | 948,824 | `f9016d95a144e100` | 800 | 3 | 8 | 2026-03-31 19:17 | no | top1 0.425 / top3 0.800 |
| `..._ranksel_depth4.json` | 1,431,592 | `a46b0c223fe9fd61` | 800 | 4 | 8 | 2026-03-31 20:04 | no | top1 0.575 / top3 0.875 |
| `..._ranksel_child5.json` (was live) | 1,196,516 | `527dc49aea109487` | 1000 | 3 | 5 | 2026-03-31 20:51 | **no** | **never ran (aborted sweep)** |

`xgb_player_level_cs2cd_ranksel_base.json` is a **byte-identical copy** of the canonical model (same sha256, max abs `predict_proba` difference = `0` over 600 rows), i.e. that arm of the rank-selection experiment was a no-op control.

### 9.3 Controlled comparison - grouped 5-fold OOF on the frozen training table

Command: `python main/scripts/evaluate_xgb_gridcv.py --train-data cs2cd --artifact-stem <stem> --xgb-jobs 4` on `player_features_cs2cd.parquet` (sha `de13fd65a7acf7a8...`, 6973 rows / 882 demos; after the `n_players>=8` filter 6886 rows / 860 demos, 992 pos / 5894 neg). Same features, same folds, same protocol for all four, so this is the only fully controlled comparison that includes `child5`. Copies in `processed/reports/_model_compare_20260919/`.

| Artifact | PR-AUC | ROC-AUC | CDemo top1 | CDemo top3 | FP@0.50 non-cheater demos | ECE raw -> calibrated |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `xgb_player_level_cs2cd` (pinned) | 0.7926 | 0.9557 | 0.9283 | 0.9659 | **84** | 0.0353 -> **0.0023** |
| `..._ranksel_base` | 0.7926 | 0.9557 | 0.9283 | 0.9693 | 106 | 0.0353 -> 0.0353 (no calibrator) |
| `..._ranksel_depth4` | 0.7898 | 0.9565 | 0.9181 | 0.9693 | 97 | 0.0306 -> 0.0306 |
| `..._ranksel_child5` | 0.7941 | 0.9559 | 0.9283 | 0.9727 | 101 | 0.0305 -> 0.0305 |
| *documented 8/19 canonical run* | *0.8051* | *0.9589* | *0.9283* | *0.9795* | *84* | *0.0358 -> 0.0043* |

Reading: `child5` leads PR-AUC/top3 by `+0.0015` / `+0.0068` (noise-level) but flags ~20% more non-cheater demos at 0.50 and has no calibration; `depth4` is the only one with a higher ROC-AUC (`+0.0008`) while losing top1, PR-AUC and FP. No variant is *materially* better than the canonical model, and only the canonical model is calibrated and documented.

### 9.4 Benchmark-slice evidence (rank of the known cheater, calibration-independent)

Computed from the surviving per-demo `ranked_players_infer.csv` files, same 40 cheater demos, metric = rank of the labelled SteamID by `risk`:

| Artifact | top1 | top3 | median rank | source |
| --- | ---: | ---: | ---: | --- |
| `xgb_player_level_cs2cd` | 0.600 | 0.900 | 1.0 | `BENCH_CHEATER_Demo1..40` |
| `..._ranksel_depth4` | 0.575 | 0.875 | 1.0 | `RANKSEL_DEPTH4_CHEATER_Demo1..40` |
| `..._ranksel_base` | 0.425 | 0.800 | 2.0 | `RANKSEL_BASE_CHEATER_Demo1..40` |
| `..._ranksel_child5` | - | - | - | sweep aborted, no cheater bucket |

Version-consistent batch only (`3/31 19:17-20:50`): `depth4` 0.575 > `base` 0.425. Non-cheater slices (`NORMAL`/`PRO`, 40 each) were clean for all three: 0 demos above 0.20 or 0.50.

### 9.5 New findings from Phase 1c

| # | Sev | Finding | Evidence |
| --- | --- | --- | --- |
| F31 | S2 | **Cross-sweep benchmark numbers are not comparable.** `..._ranksel_base.json` is byte-identical to the canonical model yet scored 0.425 vs 0.600 on the same 40 cheater demos, because the harness changed between sweeps (`score_benchmark_suite.py` mtime 3/31 10:48, i.e. after the canonical `BENCH_*` sweeps at 3/30 20:25-3/31 10:00 and before the ranksel sweeps at 19:17-21:17) and `BENCH_*` dirs are themselves a mix of 3/30 and 3/31 builds (`BENCH_CHEATER_Demo1` was refreshed at 3/31 21:54). Any promotion/rejection decision based on raw cross-sweep top1 deltas is confounded. | sha equality + max-proba diff 0; manifest mtimes; per-batch top1 recomputation |
| F32 | S1 | **Only the canonical stem has a calibrator.** `load_calibrator` returns `None` unless `<stem>_calibration.pkl` exists, so each ranksel artifact served **uncalibrated** probabilities and `risk == raw`. Controlled effect on the same table: 84 -> 101/106 non-cheater demos at/above 0.50, ECE 0.0023 -> 0.0305/0.0353. Direct artifact evidence: `RANKSEL_*` rows have an empty `proba_calibrated`; `BENCH_*` rows carry a calibrated value. | `load_calibrator` code; eval summaries; `ranked_players_infer.csv` field dumps |
| F33 | S2 | **The documented eval numbers are not reproducible.** Re-running the documented OOF protocol on the same frozen table with the unchanged script gives PR-AUC 0.7926 / ROC-AUC 0.9557 / top3 0.9659 vs documented 0.8051 / 0.9589 / 0.9795. Environment drifts (`xgboost 3.0.5`, `sklearn 1.7.1`, no version pins in the repo) while inference output itself stays bit-identical, so the sensitivity is in the fold-retraining path. Metrics need pinned dependencies plus a recorded environment stamp (Phase 4c). | two runs, identical script/table/params/seed |
| F34 | S1 | **The live model had no cheater-slice validation.** The `child5` sweep (`reports/benchmark_suite_20260331_205104/`, started 20:51:04) aborted: the summary dir is empty, 76/120 per-demo dirs exist (40 `NORMAL` + 36 `PRO`) and the cheater bucket ran 0/40. Other aborted runs: `benchmark_suite_20260329_154251`, `20260330_202435`, `20260331_125724` (empty dirs). | directory listings; per-bucket counts |

### 9.6 Next step

1. Phases **2a/2b/2c** and **3a** are closed (section 10). Continue with **3b/3c** (match-load caching, vectorised temporal build), then **4a-4c** and **5**.
2. Pending owner calls: **F30** (delete the 330 orphaned rank-selection report dirs - they are now the raw material for F31/F32 analysis, so keep them until 9.6.3 is decided) and whether to open the `depth4` research lead.
3. Optional research lead, do **not** change the default for it: re-benchmark all four artifacts in **one** harness version on **one** feature build (a single controlled 40-demo sweep), because the existing evidence is harness-confounded (F31) and `child5` was never measured. Only a clean sweep may justify replacing the pinned artifact.
## 10. Session evidence: phases 2a-2c, 3a, storage and docs (2026-09-19, second pass)

### 10.1 Phase 2a - de-duplication (F10, F11)

New shared modules, byte-identical semantics preserved:

| New module | Replaces | Call sites updated |
| --- | --- | --- |
| `main/src/utils/console.py::safe_print` | 4 identical copies (`safe_print` / `_safe_print`) | `aggregate_player_features.py`, `explain_demo.py`, `infer_demo_from_path.py`, `score_benchmark_suite.py` |
| `main/src/utils/sample_weights.py::build_sample_weights` | 2 copies (train returned `Series`, eval `ndarray|null`) | `train_xgb_gridcv.py`, `evaluate_xgb_gridcv.py` |
| `main/src/utils/parquet_io.py::write_df_to_parquet` | 2 identical one-liners | `parse_demos_awpy_api.py`, `infer_demo_from_path.py` |
| `main/src/utils/demo_labels.py` (`_split_steamids`, `ensure_columns_pl`) | byte-identical copies in `aggregate_player_features.py` | aggregation imports them now |

**Equivalence proof for the sample-weight consolidation.** `sample_weight=None`,
`np.ones(n)` and `Series(1.0)` were fitted with the canonical 449-feature params on the
`n_players >= 8` table (6,886 rows, 992 positive): `max |p1 - p2| = 0.0` and
`np.array_equal` true in both comparisons. Standardising on `ndarray | None` is therefore
bit-safe, including for the training path that previously passed an all-ones `Series`.

**Deliberately NOT consolidated** (documented divergence, not duplication):
`load_cheater_map`, `demo_base_label` and `label_demo_frame_pl` differ between
`demo_labels.py` and `aggregate_player_features.py` (warning prints and extra column
aliases such as `attacker_steamid` / `cdemo`). `_load_local_module` in
`train_encounter_nn.py` is a re-implementation that exists to bootstrap without package
imports; unifying it would change that script's import strategy for ~5 lines of gain.

### 10.2 Phase 2b - orphan branch retired (F5)

`main/src/parse/build_events_from_zips.py` deleted, and `PROCESSED_DEMOS_ROOT` removed
from `project_paths.py` (its only consumer). A repository-wide scan for
`build_events_from_zips` and `PROCESSED_DEMOS_ROOT` after the change returns no hits in
`main/`; the remaining mentions are generated desktop-bundle copies and the stale
`backend_manifest.json`, both regenerated by `prepare-desktop-backend.ps1`.

### 10.3 Phase 2c - the 449-feature contract is now default-locked (F3)

`training_mode.default_feature_list_path()` resolves the contract in this order:
**mode contract file first** (`xgb_player_level_cs2cd_features.txt`), then an explicit
artifact-stem feature file. Training and evaluation both record the resolved path in
`*_best_params.json` and `*_training_manifest.json`.

Measured proof (temporary `TEST_20260919_featurelock` stem, artifacts deleted afterwards):

| Run | Feature list source | Feature count |
| --- | --- | ---: |
| default | mode contract, `xgb_player_level_cs2cd_features.txt` | **449** |
| `--no-feature-list-lock` | auto-select all numeric columns | **463** |

The 14-column silent drift is real and is now impossible by accident. A design hazard was
found and fixed during verification: with stem-file precedence, a file written by the
*unlocked* run was picked up by the next locked run (463 instead of 449). Mode-contract
precedence removes that, and training now warns when a stem-local list exists but is not
the contract.

### 10.4 Phase 3a - training/inference aggregation parity (F4)

`infer_demo_from_path.aggregate_single_demo_features` was 122 lines of copied
feature math (`laplace` rates, weapon splits, `*_w`, `rt_iqr_80`, `dist_tail`, `*_shrunk`,
demo norms). It is now a 57-line delegation to
`aggregate_player_features.aggregate_kill_and_encounter_frames`, mirroring
`run_infer_pipeline.py`, which was already correct.

**A/B evidence** (old implementation taken from `git show HEAD:...`, new from the working
tree, both executed on the same engagement parquet files, players aligned by SteamID):

| Demo | Players | Shared numeric cols | Differing | New-only | Old-only |
| --- | ---: | ---: | ---: | ---: | ---: |
| BENCH_CHEATER_Demo10 | 8 | 87 | 3 | 13 | 4 |
| BENCH_CHEATER_Demo11 | 10 | 87 | 4 | 13 | 4 |
| BENCH_CHEATER_Demo12 | 10 | 87 | 4 | 13 | 4 |
| BENCH_CHEATER_Demo13 | 10 | 87 | 0 | 13 | 4 |
| BENCH_CHEATER_Demo14 | 10 | 87 | 4 | 13 | 4 |
| BENCH_CHEATER_Demo15 | 6 | 87 | 7 | 13 | 4 |

Drift was in **contract** features: `dist_p90` / `dist_tail` (up to 10.6 px), `rt_iqr_80`
(up to 19 ticks), `rt_p10_shrunk`, `rt_p90_shrunk`, `dist_tail_pct`, `dist_tail_z`.
Root cause: the copy used different quantile interpolation than the canonical
`quantile(0.90, interpolation="nearest")`. The old path also filled 13 canonical columns
with 0.0 (including `max_thrusmoke_streak`, entropy and weapon-share features), and the
4 columns it produced that the canonical does not (`multi_kill_round_rate`,
`late_round_cut`, `late_round_kill_share`, `late_signal_share`) are **not** in the 449
contract - they only feed internal style scores.

Residual, reported rather than hidden: after delegation a demo still lacks 361 contract
features, 360 of which are the encounter (`enc_*` / `enn_*`) family that requires the
window-model step, plus `aim_process_global_score`. That count is dominated by design, not
by drift; `score_demo` now prints a warning listing absent contract features instead of
silently scoring them 0.0. The light CLI remains encounter-free by design; use
`run_infer_pipeline.py` for complete rows.

### 10.5 Storage reclaimed this pass

| Item | GB | Why safe |
| --- | ---: | --- |
| `main/ui/web/src-tauri/target` | 8.69 | Rust build output, gitignored, regenerated by `cargo`/Tauri |
| `main/ui/site/.next` | 0.18 | Next.js build cache |
| `main/ui/{site,web}/tsconfig.tsbuildinfo` | ~0 | incremental build state |
| `__pycache__` (18 dirs), `.pytest_cache` | ~0 | bytecode/cache |
| empty `Demos/`, `raw_zips/`, `processed/` | 0 | no files inside |
| **total** | **8.87** | |

`NewAnubisTri/.venv` was explicitly kept: `run_pipeline.py` runs the pipeline through
`newanubis_venv_python()`, so deleting it would break every entry point.

Owner decisions taken after this inventory (see 10.8): `huggfacedata` 96.4 GB of which
**47.4 GB is the clone's own `.git`** (public HF dataset, so re-downloadable), 
`huggfacedata` working tree 49.0 GB, `LegitDemos` 63.8 GB of source `.dem` files
(already parsed into `parsed_zips/`, but not re-downloadable), `CheaterDemos` 10.6 GB
(irreplaceable labels - keep), `main/data/raw_uploads` 4.0 GB.

### 10.6 Documentation pass

`README.md`, `METHODOLOGY.md`, `PIPELINE.md` and `RESULTS.md` were rewritten in plain
language and shortened (README no longer assumes the reader knows what a CNN channel is;
PIPELINE documents the pinned artifact, the default feature lock and the retired orphan
script). A private, gitignored reference sheet was added at
`docs/personal_pipeline_guide.md` covering folder map, stage-by-stage commands, guardrails,
glossary, Q&A and open items.

### 10.7 Still open after this pass

1. **3b/3c** (match-load caching, vectorised temporal build) - unchanged from 9.2.
2. **4a-4c** (CS2CD orchestrator, smoke tests + determinism guard, dependency pins) -
   F33 reproducibility and F27 remain.
3. **5** docs/dedup follow-ups: the two engagement builders still share `wrap_deg`,
   `aim_error_deg`, `build_pair_tick_table`, `_quantile/_mean/_std` (F9), and the
   aggregated player table is still re-prepared in `analyze_*`, `calibrate_model` (F12).
4. Owner calls still pending: **F30** (orphaned rank-selection report dirs) and the
   **depth4** lead.
5. Re-run `prepare-desktop-backend.ps1` so the bundled backend inherits the pinned model
   artifact and drops the deleted orphan script.

---
### 10.8 Dataset clone history reclaimed (owner decision, executed)

The owner chose the narrowest option: delete only the clone's own `.git`, keep the extracted dataset.

| Item | Before | After |
| --- | ---: | ---: |
| `huggfacedata/.git` | 47.42 GB (827 files) | deleted |
| `huggfacedata/no_cheater_present` | 956 files, 33.80 GB | unchanged |
| `huggfacedata/with_cheater_present` | 634 files, 15.21 GB | unchanged |
| `huggfacedata` total | 96.43 GB | **49.01 GB** |
| C: free | 283.5 GB | **330.9 GB** |

Integrity evidence: file counts and byte totals were identical before and after, and sample hashes
matched - `no_cheater_present/0.parquet` `4B7886214B3CD9B6999A...`,
`with_cheater_present/0.parquet` `B1DE844081C7F4C1447F...`. The folder now carries a
`CLONE_NOTES.md` with the origin URL, the inventory and the re-clone command.

Combined reclamation this pass: **56.29 GB** (8.87 GB build output + 47.42 GB clone history).
Deliberately retained: `NewAnubisTri/.venv` (the pipeline interpreter), `CheaterDemos`
(irreplaceable labels), `LegitDemos` (source `.dem`, not re-downloadable), `parsed_zips`
(parsed tables), `tris` (map geometry).

Provenance note: `AUDIT.md` was rewritten by an external process about a minute after commit
`b8e221f`, corrupting one unrelated paragraph at line ~122 (wrapped mid-word, `Root-lev` / `el`).
The file was restored from the commit and section 10 content was not affected. If that re-wrap
reappears, it is not coming from the pipeline.


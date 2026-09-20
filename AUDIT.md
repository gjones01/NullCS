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
| 1c pin/lock the inference model artifact (F2) | next |
| 2a dedupe identical helpers, 2b retire orphan `build_events_from_zips.py`, 2c lock the 449-feature list (F3) | pending |
| 3a inference/serving aggregation parity (F4), 3b match-load caching (F6), 3c vectorise temporal build (F7) | pending |
| 3d dataset hygiene | **done** (~193.2 GB reclaimed) |
| 4a CS2CD orchestrator, 4b smoke tests + **fix the determinism guard (F27)**, 4c dependency honesty (F17/F20/F21/F26) | pending |
| 5 docs rewrite (`PIPELINE.md`, `AGENTS.md`) | pending |

Awaiting a go/no-go only for: **1c** (changes which model inference uses - requires confirmation that `xgb_player_level_cs2cd` is the intended production model, per D2) and **F30** (delete the 330 orphaned rank-selection report dirs).
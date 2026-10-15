# Research notes

Updated October 15, 2026.

NullCS turns CS2 demo data into a ranked list of players for replay review.
The desktop beta works locally. The next model is still being tested.
See [results](RESULTS.md) for the current internal benchmarks.

## Why we rebuilt the evaluation

The released CNN and the features used to train XGBoost come from different
training runs. We could not recover the older neural model, so we cannot fully
reproduce how those XGBoost training features were made.

Holding a match out of XGBoost training did not necessarily keep it out of CNN
training. That can make test results look better than they would on new matches.
This is called data leakage.

An older calibration file also used predictions from a different evaluation run.
The calibration script now requires an explicit --oof-path when both CSV and
Parquet prediction files exist, rather than silently choosing one. An explicit
file choice still needs verification against the intended model and training run.

## How the new evaluation works

We ran five grouped test folds. Each match and its overlapping encounter windows
stay in one group. Known repeated players and duplicate matches are grouped together.
Anonymous player IDs still prevent us from checking every repeated player.

Within each fold, separate data is used for training, calibration and testing.
CNN features for XGBoost training are generated out of fold: the CNN producing
each training row has not trained on that row's group. Preprocessing and reference
statistics use only training data. Test groups do not fit any stage.

The run kept 128 ticks before and 16 after the encounter, sampled into 32 CNN
observations. Four CNN epochs and the existing XGBoost settings were fixed before
reading results. The [experiment matrix](research/encounter_context_matrix.csv)
separately varies context duration, before/after allocation and observation count.
The other configurations have not been trained.

The research version fixes a row-order error in two conditional CNN summaries
and saves training reference values for inference. These changes apply only to
an explicitly declared new model bundle. Released weights keep their original
feature calculations and scoring behavior.

## Why the new model is not in the installer yet

Calibration turns model scores into estimates based on labeled examples.
The new calibration produced exactly zero for 40 positive test records and exactly
one for 42 negative records. Its log loss got worse despite a better Brier score.
We have not hidden those failures by clipping scores or tuning on test results.

The October 15 follow-up compared methods on development data. All five folds
selected sigmoid calibration, which improved test log loss and removed those exact
zero/one errors. It also missed more positive records at a fixed 0.5 cutoff than
isotonic did. See [the comparison](RESULTS.md#calibration-follow-up-october-15).
This is a better candidate for further testing, not a newly released model.
The existing desktop model and installer remain unchanged.

## Checks and performance

- The API/research suite passed 101 tests, including calibration input selection,
  grouped method selection, label isolation and false-positive denominators.
- The full patch-14153 parser check passed, including required model columns.
- Repeating one training fold produced identical CNN weights and predictions on
  this machine. This is not a guarantee across hardware or library versions.
- A real demo produced eight scored players out of ten participants; two lacked
  the required evidence. Repeated inference scores matched exactly.
- Removing redundant aggregation work reduced a measured 100-group workload from
  6.85 seconds to 0.29 seconds, with identical retained values. This is not a
  full-demo speed claim.

## Remaining limits

Historical labels have not all been independently reviewed. This dataset already
influenced feature and model choices, so internal testing does not replace a test
on new matches. Some player identities are unknown; one connected group contains
95 matches.

demoparser2 0.41.4 has a known stale user-command-value issue. Column checks cannot
prove every value is fresh. The released calibrator also reports a scikit-learn
version warning. Neither issue was hidden by upgrading dependencies.

## Reproduce the run

Use Python 3.13 and the pinned desktop dependencies. CUDA is optional; the recorded
training run used an isolated CUDA PyTorch installation on an RTX 5060 Ti.
The desktop uses CPU inference. Dataset files are not in the public repo.
Use new output directories; never overwrite the released model folder.

```powershell
python main/scripts/prepare_corrected_baseline.py --data-root <data-root> --output <input-dir>
python main/scripts/train_corrected_baseline.py --input <input-dir> --output <fold0-dir> --fold 0 --device cpu
# Repeat for folds 1 through 4, each in a new output directory.
python main/scripts/summarize_corrected_baseline.py --input <input-dir> --folds <fold0> <fold1> <fold2> <fold3> <fold4> --output <summary.json>
python main/scripts/check_corrected_reproducibility.py --first <fold0> --repeat <repeat-fold0> --output <check.json>
python main/scripts/validate_calibration.py --input <input-dir> --folds <fold0> <fold1> <fold2> <fold3> <fold4> --output <new-calibration-dir>
```

Run manifests record source hashes, model hashes, settings and group assignments.
The older-file checks remain available in check_artifact_lineage.py. The detailed
October 14 investigation remains in Git history; this shorter note replaces it
as the current explanation.

## Sigmoid integration check

The fixed fold-0 model was exported with the sigmoid method selected by its
development-data comparison. It remains an experimental integration candidate,
not a final model trained for release. Export replays the calibration decision,
checks the parent run, and records the calibration report hash in the bundle.

Two real demos completed with 8 and 10 scored players. Their raw model scores
matched the earlier fold-0 runs exactly; only calibration and resulting review
scores changed. The desktop API also completed a real analysis, returned the
same report as the CLI, and rejected unauthenticated intake and result requests.
The checks used the actual pipeline, not mocked predictions.

The original float32 calibration predictions replay exactly. The production
float64 scoring boundary differs by at most 0.000000081 on this fold; export checks
that the difference stays below one float32 epsilon and records the measurement.

The packaging script now carries the required model contract with corrected
bundles. A source-resource packaging run verified all eight model file hashes.
No frozen executable or installer was built in this check, and no production
weights were replaced. A final training run and packaged-app verification still
separate this integration candidate from a release.

To repeat the export after the calibration comparison:

```powershell
python main/scripts/export_corrected_validation_bundle.py --fold <fold0> --input <input-dir> --calibration-validation <calibration-dir> --output <new-model-dir>
```

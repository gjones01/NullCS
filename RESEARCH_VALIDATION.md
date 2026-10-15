# NullCS: initial scientific investigation — 14 October 2026

Status: research branch `research/validation-20261014`, based on public source `c765dac`.
Follow-up: [Artifact lineage and corrected baseline protocol](ARTIFACT_LINEAGE_BASELINE.md)
contains the deeper forensic checks and supersedes this document's preliminary experiment
matrix/split proposal. In particular, the original neural generator remains unidentified;
the historical player table must not be assumed to have used the currently released CNN.
This initial investigation did not release, deploy, replace production models or train.
The subsequently authorized corrected baseline and current release decision are recorded
in section 9 of `ARTIFACT_LINEAGE_BASELINE.md`; read that section for the latest measurements.
Worktree: `C:/ClarityCS/.tools/publish-beta`. The original working tree is preserved.
Private measurements are under `C:/ClarityCS/main/data/research_validation_20261014/`;
do not publish that folder: it contains demo copies, player identities and feature vectors.

**Observed** means inspected code/artifacts or an executed measurement below.
**Hypothesis** needs an experiment. **Recommendation** is a proposed decision.
**Unknown** means this investigation cannot support the claim yet.

## Evidence-backed execution plan

1. Inspect the serialized temporal model and ordered channel/feature contracts.
2. Reproduce the reported missing-player demo and add observational coverage diagnostics.
3. Recompute saved-score metrics, isolate calibration reuse, and audit artifact lineage/splits.
4. Run the unchanged predictive stack twice, build a reusable local cohort harness, test diagnostics.
5. Design versioned window experiments and bounded hardware measurements.
6. Require owner approval before full nested retraining, GPU environment installation, or release.

This initial investigation completes those diagnostic steps. It does **not** claim a new,
fully independent evaluation of the complete stack. That requires the controlled training
and label/split decisions in J.

## A. Current architecture and verified production artifacts

`.dem -> demoparser2 telemetry/events -> kill + encounter frames -> shared aggregation`
`-> temporal CNN encounter scores -> 12 neural aggregate features -> XGBoost`
`-> sibling calibrator -> evidence downweight -> ranked CSV -> desktop result JSON -> UI`

Exact implementation references (relative to this worktree):

| Boundary | Source / function | Finding |
|---|---|---|
| Desktop invocation | `main/ui/api/desktop_sidecar.py`; `main/scripts/run_infer_pipeline.py:main` | Canonical raw-demo entry point; explicit model override supported |
| Parser | `main/src/adapters/demoparser2_local.py:load_demo`, `_ticks_table` | Death, bullet damage, weapon fire and round events; required model columns fail closed; decorative omissions are warned |
| Dataset adapter | `main/src/adapters/cs2cd_adapter.py:load_match`, `_extract_cheaters` | Preparsed dataset uses its JSON labels and upstream telemetry; not today's local parser |
| Windows/features | `main/src/features/build_cs2cd_engagement_features.py:build_match_outputs`, `build_encounter_rows`, `build_kill_rows` | Local and dataset paths share feature code; input provenance differs |
| Aggregation | `main/src/features/aggregate_player_features.py:aggregate_kill_and_encounter_frames` | Eligibility and handcrafted summaries; shared code does not guarantee equal reference populations |
| Neural inference | `main/src/models/encounter_nn.py:build_temporal_sequences_for_demo`, `load_trained_encounter_model`, `aggregate_encounter_scores` | 35 ordered channels, 32 resampled observations; 12 `enn_*` summaries |
| Player scoring | `run_infer_pipeline.py:_infer_scores`; `src/utils/scoring.py` | XGBoost output, optional calibration, existing downweight, sort by risk |
| Desktop contract | `main/ui/api/desktop_result.py:read_result`; `main/ui/web/src/DesktopApp.tsx` | Reads canonical ordered CSV; no eight-player UI cap |

Loaded actual artifacts successfully. The temporal checkpoint is a **104,417-parameter CNN**:
Conv1d 35→64 (kernel 5), 64→96 (kernel 5, dilation 2), 96→128 (kernel 3, dilation 4),
each followed by BatchNorm/GELU; dropout 0.15; temporal mean/max pooling concatenated;
Linear 256→96, GELU/dropout, Linear 96→1. Sigmoid converts its logit to an encounter output.
The checkpoint and preprocessor both declare sequence length 32; their channel orders match.
`hidden_dims` stored in the checkpoint is an MLP-oriented field, not the instantiated CNN architecture.

XGBoost has 449 serialized features and the file order exactly matches its training manifest.
The logical contract hash (UTF-8 names joined by LF, **no trailing LF**) is
`2ec454a76460f2ab339b6648847cedaf29e873172dabc60bc041e6f0f56098a8`.
The physical file hash differs because encoding/newlines are a different hash convention.

| Artifact | SHA-256 |
|---|---|
| `encounter_nn_cs2cd.pt` | `1e990d5a0e77f5990002fe8e16d2f808fa8c4b6f6d356de7081548e77afc0dd0` |
| `encounter_nn_cs2cd_preproc.pkl` | `bcf7c0a9404479ac69962bba56ce60b1789aac73620c89be55ed163fd0ae51df` |
| `xgb_player_level_cs2cd.json` | `f9016d95a144e1004f40c01f15b86879d9d9101cdda4659acaa261ac80610ea8` |
| `xgb_player_level_cs2cd_calibration.pkl` | `f36afda6a922f0a22b1617e75b05af8d8800026f5a52b5598c8d713fc9667adf` |

All four match the existing desktop bundle resources. All six audited production model/
preprocessor/feature/calibrator files retained their original hashes after the investigation.
The active artifact is `encounter_nn_cs2cd.pt`, not a filename containing `temporal_seq32`.

Observed release environment: Python 3.13.5, torch 2.13.0+cpu, demoparser2 0.41.4,
AWPy 2.0.2, scikit-learn 1.9.0, XGBoost 3.3.0, pandas 3.0.5, NumPy 2.5.1.
The older research environment has torch 2.11.0+cpu. Neither supports CUDA currently.

### Material research discrepancies — promotion blockers

1. **Temporal-to-player artifact lineage is inconsistent.** XGBoost's manifest is dated
   March 29; the current temporal manifest April 16. All 6,973 joined player-table rows
   differ in `enn_score_mean` from the current temporal OOF aggregate file; other neural
   columns also differ extensively. Chronology alone is not proof of failure, but this
   value comparison establishes that they are not the same generated feature set.
   The old training table must not be silently regenerated. Recover the original neural
   checkpoint/cache or evaluate a newly versioned, correctly nested complete stack.
2. **Historical OOF CSV and Parquet disagree on every matched raw prediction** across
   the same 6,886 player-match keys. Calibration code prefers Parquet. Website/desktop
   reference data used CSV. Neither should be called an independent shipped-stack benchmark.
3. **Population-dependent preprocessing:** aggregation computes global RT/distance medians
   over its input population for four `*_shrunk` contract features (around lines 939–947).
   Training aggregates the research population before CV; inference aggregates one demo.
   This is both a train/inference reference mismatch and transductive validation information.
   Shared code prevented copied formulas, but did not fix the statistical reference.
4. **Stacked CV is not nested.** Temporal OOF features are generated separately from the
   outer XGBoost evaluation. Training-row neural features may depend on labels in the
   outer test fold. Demo grouping each stage independently does not make the stack held out.
5. **Early stopping/model selection reuse:** temporal fold validation AP selects the epoch
   then reports that fold's performance; XGBoost search and later evaluation reuse the data.
   Historical OOF metrics therefore include selection optimism.

No speculative fixes to these research behaviors were applied.

## B. Missing-player investigation and diagnostic fix

Reproduced the exact supplied file locally:
`C:/Program Files (x86)/Steam/steamapps/common/Counter-Strike Global Offensive/game/csgo/replays/match730_003848264343296672039_0024171916_123.dem`.
167,548,555 bytes; SHA-256 `4a19f7d71414317d44e1afc55ffb86f6f2f6833f0e650a3ba141926164cdc0ff`.
Map Mirage, demo patch 14190. No labels were assigned.

| Stage | Observed count |
|---|---:|
| `parse_player_info()` | 10 |
| Tick/event participants | 10 |
| Participants with encounters | 10 |
| Aggregation eligible | 8 |
| Scored / serialized | 8 |

All ten had 100,668 tick rows. One excluded participant had 4 kill rows, 4 valid RT kills and 22 encounters;
the other had 3, 3 and 24 respectively. The canonical filter requires
`n_kills_with_rt >= MIN_KILLS`, where `MIN_KILLS=5`. This is not a requirement of five
encounters or five total kills. The other eight players survived. **The two omissions are
explained by aggregation eligibility, not parser disappearance or rendering truncation.**

Changes on the research branch:
- `player_coverage.py` records participant metadata, tick/event presence, kill and RT counts,
  encounter counts, eligible/scored status and explicit exclusion reason.
- Parser attaches optional participant metadata without altering model input frames.
- Pipeline writes `player_coverage.json` before aggregation and alongside successful reports.
  If scoring fails, pre-scoring diagnostics remain available locally; the analysis still fails.
- Desktop JSON adds optional coverage, and the UI/text export lists **Not Scored** participants.
  Old reports remain readable, with a coverage-not-recorded warning.

Coverage is not a claim to reconstruct an entire roster: unrecorded connects/disconnects,
bot identities and incomplete demos can limit it. Tick rows alone do not prove usable
encounter evidence. Name changes can split canonical grouping keys; candidate-count versus
eligible-row disagreement is explicitly flagged instead of changing grouping semantics.
No fabricated scores, forced ten-player assumption, or eligibility relaxation.
The installed beta executable has **not** been rebuilt with this fix.

## C. Scores and calibration

`model_score` = XGBoost positive-class `predict_proba` output, not its raw margin/logit,
percentile, or a demonstrated real-world cheating probability. Class weighting and sampled
labels affect its probability interpretation.

`calibrated_probability` (legacy contract name) = sibling isotonic map applied to that output,
when present. Isotonic regression has flat regions, so different model outputs legitimately
map to the same estimate. The payload contains method/model, **no model or input-data hash**;
matching filenames do not establish historical calibration provenance.

`review_score` = calibrated output when available, otherwise model output, multiplied by
0.85 when `rt_n < 8`. Thus equality to the calibrated estimate is intentional when that
downweight does not fire. Rank sorts this review score descending. Ties are not extra evidence.
The displayed evidence confidence is a clipped weighted log-count heuristic, not a statistical
confidence interval; inference CIs are not computed.

Recommendation: retain numerical semantics for compatibility, use **calibrated research
estimate** in reporting, and explicitly state that transfer to new matches is unvalidated.
The diagnostic desktop warning now says this. Avoid calling it a person's chance of cheating.

Fresh metric reproduction on the saved **Parquet** OOF predictions:

| Output | Brier | Log loss | ECE (10 equal-width bins) |
|---|---:|---:|---:|
| Raw historical OOF | 0.053246 | 0.194534 | 0.035621 |
| Saved isotonic on current OOF — not holdout | 0.047489 | 0.165012 | approximately 0 |
| New match-cross-fitted isotonic diagnostic | 0.048787 | 0.179133 | 0.004789 |

The near-zero ECE in the middle row is not evidence of perfect deployment calibration:
the calibrator is evaluated on its fitting sample. The last row fits disposable calibrators
on four match folds and evaluates the fifth; it corrects **calibrator resubstitution only**,
not upstream feature/model-selection leakage. No calibrator was saved or promoted.
`audit/reliability.png` visualizes these distinctions. Tiny or single-class map slices are
descriptive, not grounds for population-specific calibration claims.

The calibrator was serialized using sklearn 1.7.1; loading under 1.9.0 reproduces
`InconsistentVersionWarning`. No dependency upgrade or recalibration was performed.
Independent calibration/test separation follows the [scikit-learn calibration guidance](https://scikit-learn.org/stable/modules/calibration).

## D. Exact current window

`build_encounter_rows` anchors on **damage and kill events**, deduplicated by round,
attacker, victim and tick. It queries paired telemetry within `[anchor-128, anchor+16]`,
clamped at tick zero, inclusive. Attacker/victim rows must share a tick and round.
Candidate rows require both alive and aim error <=35 degrees. This is a directional
candidate criterion, **not verified line of sight**. Start/end are first/last candidate ticks;
end is capped at start+192, but the queried span is already at most 145 tick positions.
Kill-end summaries look another 16 ticks past that end. Anchor inclusion is conditional on
candidate availability. Exact identical encounter IDs are deduplicated; overlapping windows
from different damage/kill anchors remain correlated observations.

Saved temporal OOF corpus: 281,792 windows, 894 demos. Duration median 130 ticks,
10th/90th percentiles 96/145, range 1–145. Candidate row median 128, range 1–145.
No duplicate `(demo,attacker,victim,start,end)` keys in that artifact. Overlap is not thereby excluded.

Temporal extraction reselects candidate rows and interpolates **by row index** to 32 samples,
not by uniform elapsed tick time. Gaps can be compressed. A single row repeats; an empty
sequence starts as zeros and is standardized, without a missingness mask. Some inputs
forward/backfill; binary channels are interpolated too. Future shot/damage distances are
present; missing-event distance uses `seq_len*8`, an extra confound when changing sequence length.

Observed game-time probe on the supplied raw demo: ticks 10000/10064/10128 correspond to
225.03125/226.03125/227.03125 seconds: **64 Hz**. The header itself has no tick-rate field.
Two sampled source-dataset matches mostly have unit tick gaps but some missing ticks;
that alone does not prove a clock rate for all historical matches. Verify clock fields per source.

This is retrospective, outcome-anchored review. Post-event features are not automatically
invalid for that purpose, but the model cannot be described as a pre-event detector.
`v_spotted` is a visibility proxy; `visible_ratio=1` and `occluded_tick_count=0` in this
builder describe its selected candidates, not measured occlusion. Preserve these historical
definitions until an explicit feature-version migration is evaluated.

## E. Larger windows and GPU experiment design

Increasing `--seq-len` alone changes sample count, **not the encounter duration**.
The proposed 96-tick experiment can actually be shorter than many current windows.
Separate temporal extent, sample density, masking, and anchoring changes.

| Experiment | Tick extent at fixed damage/kill anchor a | Sample-count comparison |
|---|---|---|
| A | Exact released adaptive candidate window | 32; mandatory frozen baseline |
| B | `[a-48,a+15]`, 64 positions | 32 and 64 |
| C | `[a-64,a+32]`, **97** inclusive positions | 32 and 96 resampled samples; report both dimensions |
| D | `[a-96,a-1]`, 96 strictly pre-anchor positions | 32 and 96 |
| E, optional | `[a-96,a+31]`, 128 positions | 32 and 128 |

If exactly 96 original positions are desired for C, choose `[a-64,a+31]` before running;
that is 64 pre-anchor, the anchor, and 31 strictly post-anchor positions. Do not silently
call both definitions “64+32.” At the measured 64Hz, 96 intervals span 1.5 seconds.

Freeze the same anchor IDs and outer splits. Keep candidate filtering in the first
controlled comparison; separately ablate full valid paired rows plus explicit masks.
Pre-only D must exclude future-event channels and outcome-derived encounter summaries
in a separate causal feature variant; cropping ticks alone does not establish causality.
Keep a retrospective D control too, so removing future channels is not mistaken for a window effect.
Version event-distance sentinels independently of sample count. Record boundaries, missing
fractions, spacing, edge padding and overlap for every sequence. Never reuse the old cache:
its key validates row count/demo/attacker/order/channels/length, but not victims, bounds,
parser/data hash or feature-code version. New cache keys must include all of those.

Use an outer match-disjoint test, with an inner match-disjoint early-stop/tuning split.
Inside each outer training partition, generate inner OOF neural features for XGBoost;
the neural model predicting outer-test encounters sees no outer-test labels. Fit population
references on training only. Fit calibration on a further disjoint split or properly nested
OOF stage. Reserve a new chronological external cohort once; do not tune on it repeatedly.
Where authentic IDs exist, also hold out connected player/match components. Do not group
all anonymized `Player_1` rows as one real person. Source holdouts and pro-player stress
tests supplement, rather than replace, the primary evaluation.

Measure encounter AP/ROC, player AP/ROC, match P@1/P@3 and recall@K, false positives
per negative player and per match, precision at a fixed review budget, calibration,
coverage, high-skill/map/source slices, CPU latency and peak memory. Use paired
match-bootstrap differences between candidates and baseline. Report labeled coverage,
unscored positives and missing labels; do not improve metrics by dropping hard matches.

### Hardware evidence and bounded benchmark

Observed NVIDIA RTX5060Ti, driver 617.14, 16,311MiB VRAM; 10,646MiB free at observation.
Both available Python environments are CPU-only, so CUDA driver/runtime compatibility,
GPU utilization, AMP stability and peak VRAM remain **unverified**. A new isolated GPU
environment should follow the current [PyTorch installation/support guidance](https://pytorch.org/get-started/locally/),
then prove allocation, convolution forward/backward, finite loss and device placement.
Do not modify the release environment. Training currently silently chooses CPU if CUDA
is unavailable; experiment launcher must instead fail on an unmet requested device.

Bounded synthetic **CPU** AdamW/BCE forward+backward benchmark, batch128, four threads,
one warmup and five measured steps; no checkpoint written:

| Samples/window | Median step seconds | Float32 raw tensor for 281,792 x35 windows |
|---:|---:|---:|
| 32 | 0.02810 | 1.176 GiB |
| 64 | 0.05081 | 2.351 GiB |
| 96 | 0.07150 | 3.527 GiB |
| 128 | 0.09973 | 4.703 GiB |

These are kernel measurements, not GPU or whole-training timings. Current training makes
fold slices and standardized copies; peak host memory exceeds raw tensor size. Parsing,
sequence construction, validation and caching add cost. No defensible GPU training-time
estimate exists yet. After setup, benchmark real cached batches at128/256/512; test FP32
then BF16/FP16 with finite-gradient/metric checks. Tune workers/pinned-memory only from
measurements. Gradient accumulation changes optimizer batch semantics and BatchNorm
statistics; it is a separate experiment, not a free equivalent larger batch.

## F. Data, labels and feature opportunities

Observed source files: 478 nominal no-cheater matches and 317 with-cheater matches,
plus pro-legitimate data represented in the training table. The dataset's local README
explicitly warns that nominal negatives were not fully verified; positive-source matches
were manually labeled following VAC-based selection. A VAC-related collection rule is
not independent proof that every observed behavior in each match is cheating.
See the [dataset's own documentation](https://huggingface.co/datasets/CS2CD/CS2CD.Counter-Strike_2_Cheat_Detection).
The adapter labels listed cheater IDs positive and other players negative. Label reliability
therefore differs by source and is not established by a numeric label column.

Filtered player table: 6,886 rows/860 demos, 992 positive (14.41%), 5,894 negative.
Pro subset: 982 rows, all negative; nominal-negative CS2CD: 4,052 rows, all negative;
positive-source CS2CD: 1,852 rows, 992 positive. Source is strongly associated with label,
even though source/identity columns are excluded from the feature contract.

Most CS2CD IDs are `Player_1`…`Player_10`; true cross-match identity is unrecoverable
from those alone. In the real-format pro subset, 142 IDs occur in multiple matches;
reconstructed match folds share 85/76/85/79/94 such validation rows with training.
This does not measure unseen-player generalization. Full raw-file duplicate/session
provenance and label adjudication remain incomplete; exact window-key deduplication
is not a substitute. Do not interpret anonymized-ID label conflicts as mislabeled people.

Feature priorities (all hypotheses; no current contract changes):

| Candidate | Observable basis / limitations | Controlled test |
|---|---|---|
| Tick-gap/missingness masks | Tick positions available; command values may be stale | Current interpolation vs time-grid/masked model, same anchors/splits |
| Aim derivatives/overshoot | Yaw/pitch, target geometry; per-tick not subtick intent | Existing derivative group ablation before adding more |
| True visibility/occlusion | Spotted and front cone are proxies; map geometry/LOS needed | Independently validate LOS on hand-reviewed encounters before model use |
| Recoil/spray timing | View changes and shot/weapon events; mouse input reliability limited | Weapon-conditioned, duration-matched group ablation |
| Counter-strafe coordination | Velocity and shots available; sample-gap sensitivity | Context-conditioned negatives; avoid calling movement alone suspicious |
| Difficulty/high-skill baselines | Distance, movement, weapon/context available | Source-held-out and pro-only false-positive tests |
| Across-match consistency | Real SteamID + multiple independently sourced demos | Player-grouped longitudinal study; never join anonymized slots |

The parser 0.41.4 stale user-command issue remains relevant to mouse and command/view
features. A passing required-column sentinel proves presence, not correct current values.
Do not repair those values speculatively. Include command-feature ablations and compare
against independently validated parser behavior before any versioned correction.

## G. Candidate model experiments

| Priority / hypothesis | Baseline and assumptions | Cost, failure modes, adoption evidence |
|---|---|---|
| 1: corrected stacked baseline | Same CNN/XGB; immutable labels/splits | Nested fits cost more; may lower headline scores. Establish trustworthy reference first |
| 2: XGB without neural features | Same eligible population and nested protocol | Lower compute; tests whether CNN adds held-out utility rather than source shortcuts |
| 3: window B/C/D | Fixed CNN capacity first, then separately adapted capacity | More sequence storage; padding/anchor/outcome confounds. Require useful paired gains at fixed false-positive/review budget |
| 4: median/top-k/robust aggregation | Fixed encounter predictions; inner-tuned summaries | Cheap; max/top-k may amplify one bad encounter. Compare match coverage and false positives |
| 5: masked dilated CNN | Already dilated baseline; explicit missing-time hypothesis | Moderate; masks may encode source. Needs source-held-out gain |
| 6: small attention model | Needs enough independent matches, not merely many windows | Greater tuning cost/overfit risk. Must beat CNN at comparable capacity/CPU latency |
| Later: self-supervised/contrastive | Requires larger unlabeled corpus and sound augmentations | Expensive; positive pairs must not encode source/player identity shortcuts |
| Later: uncertainty/OOD | Validate failure correlation on new cohorts | Marginal shift flags or ensemble disagreement are not cheating probabilities |

No alternative was trained. Prefer a simpler model if practical results tie. Group-level
permutation/feature ablation must be done on untouched outer folds; permutation of strongly
correlated individual columns can underestimate their joint importance.

## H. Reproducible validation and executed checks

New tools in `main/scripts/`:
- `research_artifact_audit.py`: trusted artifact loading, hash/channel/parameter checks,
  historical Parquet metrics, match bootstrap, calibrator-only crossfit, lineage comparison,
  bounded synthetic benchmark and reliability plot. Output directory must be new.
- `research_demo_cohort.py`: JSON cohort manifest -> isolated copied artifacts -> canonical
  subprocess per demo -> logs, coverage, timing, predictions and labeled/unlabeled summary.
  Timeout/failures stay in the denominator. Labels must be supplied independently.
- `research_validation.py`: saved predictions -> raw-score metrics, complete-label match
  ranking, match bootstrap, map/cohort slices, optional reference-tail/missingness diagnostics.
  Rejects duplicate player-match rows and invalid scores/labels. Partial labels cannot
  define whole-match P@K. Shift rates are flags, not multivariate OOD probabilities.

Example manifest (keep it private):
```json
[{"demo_path":"C:/path/match.dem","cohort":"new_unlabeled"}]
```
Optionally add `"labels":{"REAL_STEAMID":0}` only with documented independent evidence.
Do not infer labels from a score or assume every unlisted player is negative.

Commands from this worktree, using the release Python executable:
```powershell
$py = 'C:/ClarityCS/main/data/web_validation/release-venv/Scripts/python.exe'
& $py main/scripts/research_artifact_audit.py --processed C:/ClarityCS/main/data/processed --output C:/path/new-audit
& $py main/scripts/research_demo_cohort.py --manifest C:/path/cohort.json --models C:/path/trusted-models --output C:/path/new-cohort
& $py main/scripts/research_validation.py --predictions C:/path/new-cohort/predictions.csv --output C:/path/new-metrics
& $py -m pytest main/ui/api/tests -q
```
The model directory requires both model manifests, both models, temporal preprocessor and
channel JSON, XGBoost feature list and optional matching calibration. No public uploads.

### Observed results

Historical Parquet AP **0.795570**, ROC **0.955539**. 200 match-bootstrap replicates,
seed20261014: AP 95% percentile interval **[0.738650,0.843156]**, ROC **[0.944223,0.964687]**.
These intervals describe sampling variation of saved predictions, not selection/leakage bias.
Historical CSV AP **0.805077**, ROC **0.958891**. All 6,886 joined scores differ.
Preserve both; do not substitute either for a fresh whole-stack holdout evaluation.

Supplied Mirage demo: full pipeline completed in **46.08 seconds**; second fresh cohort
run **46.51 seconds**, 8 scores/10 observed participants. No GPU. Maximum absolute
difference in raw/calibrated/review scores **0.0**; all ordered feature-vector hashes equal.
This is one-demo repeatability only. All eight raw scores were above 0.5; without trustworthy
labels this is **not** evidence of eight true positives or eight false positives.
The real artifacts passed through `desktop_result.read_result` with coverage and original
ranking preserved. New frontend compiled; installed Tauri executable not rebuilt or visually
verified in this research pass. A third latest-source cohort run and final test count are
recorded in the validation addendum below.

Initial isolated run failed because this investigation's copied model directory omitted
the temporal training manifest. The guard rejected missing neural signals. Supplying the
unchanged required manifest fixed the setup; no model fallback/zero filling was introduced.
This is an experiment setup failure, not a demonstrated failure of the shipped app.

Full patch14153 sentinel re-run: **passed**, 1,089,620 rows, 30 columns. No pin updated.
Existing API/security/parser rejection tests plus new diagnostics/metrics tests passed;
see addendum for final exact count. Frontend `npm.cmd run build`: passed.
PowerShell's `npm.ps1` policy blocked the first invocation; using `npm.cmd` required no policy change.
Feature-shift diagnostics executed on the eight current rows versus historical player table;
sample is too small, and reference lineage too uncertain, for a calibrated OOD claim.

## I. Cross-match architecture proposal — not implemented

Local batch queue -> existing single-demo engine -> immutable model/parser-versioned
player-match records -> SteamID-linked longitudinal summaries -> analyst report.
Deduplicate demos by content/match fingerprint before accumulating evidence. Store hashes,
coverage, source, timestamp, score distribution, evidence counts and model versions;
keep raw demos separately with user-controlled deletion. No automatic uploading.

Report distributions and persistence across independent matches, not a product of calibrated
probabilities or a fabricated combined confidence. Model/patch changes break comparability.
Start with per-player median/IQR, fraction above a predeclared review cutoff, coverage and
effective independent match count. Compare with a single-match baseline on player-disjoint,
chronological evaluation. Determine minimum evidence from validation, not an arbitrary number.
Connected sessions and repeated opponents require clustered uncertainty. Genuine real IDs
are necessary; never link anonymous `Player_1` across dataset files.

## J. Priorities, decisions and education

1. **Resolve artifact lineage and evaluation file disagreement** before claiming benchmark
   quality for the released stack. High scientific importance, low compute for provenance work.
2. **Establish trustworthy labels and frozen splits**, including high-skill negatives and
   independent external demos. Highest protection against false conclusions; human review needed.
3. **Approve a corrected nested baseline** with training-only population references and
   documented stage cross-fitting. This is research methodology change and substantial training.
4. **Approve isolated GPU environment setup and a bounded real-batch benchmark**. No release
   dependency changes. Then estimate training cost from measured throughput and preprocessing.
5. **Approve B/C/D window experiments** after baseline and resource estimates; A remains pinned.
   Decide inclusive97-position vs exact96-position C and retrospective versus causal D.
6. **Approve a diagnostic desktop release separately** after packaging/UI regression validation.
   Current source changes are not in the installed executable; no release was published.

Proposed promotion gate: predeclare acceptable high-skill false-positive rate and review
budget with the owner; require a useful paired improvement without material coverage,
calibration, source-generalization, CPU-latency or memory regression. Do not select the gate
after viewing test results. Store immutable dataset/config/split/code/artifact hashes and
all seeds. Repeat seeds to separate training variance from match-sampling variance.
Rollback keeps the current release bundle and report schema intact, points back to its
signed/versioned artifact set, and never overwrites previous reports or calibrators.

Key concepts:
- **AP versus ROC:** ROC measures ranking across positives/negatives; AP is more sensitive
  to the positive prevalence and review precision. Neither supplies a usable cutoff by itself.
- **Calibration:** among outputs near a value, how often does the research label occur?
  This depends on labels and population prevalence. It is different from ranking well.
- **OOF versus nested OOF:** a row can be held out of XGBoost while its engineered neural
  inputs still depend indirectly on test-fold labels. The entire learned chain must be held out.
- **Bootstrap:** resample matches to respect within-match correlation. It estimates sampling
  uncertainty, not bias from noisy labels, reused test sets, or wrong artifacts.
- **Ablation:** change one cause at a time. More ticks, more samples, a new mask and larger
  architecture together cannot tell us which change helped.
- **Coverage:** reported precision on selected players does not describe players omitted by
  eligibility. Report both score quality and who could not be evaluated.

Outstanding unknowns: independently adjudicated external accuracy; corrected whole-stack
holdout metrics; full source/session duplicate audit; reliable player separation in anonymized
data; original temporal artifact underlying the XGBoost table; GPU compatibility/throughput;
large-window missingness and CPU inference cost; general determinism and production capacity.

### Validation addendum and changed files

- Final API test suite: **84 passed**, 23.21 seconds, one existing Starlette/httpx deprecation
  warning. Includes required-column rejection/security tests and new coverage, metadata-only
  participant, legacy-report compatibility, invalid-score, duplicate, unlabeled, bootstrap
  reproducibility and calibration-bin boundary tests.
- Latest metadata-enabled cohort run: **47.1989 seconds**, completed, 10 observed / 8 eligible /
  8 scored / 2 unscored. Stored real results served by FastAPI TestClient: unauthenticated
  **401**, authenticated **200**, counts verified. This is an actual-artifact API test,
  not a newly packaged desktop UI test.
- Missing input and corrupt `.dem` cohort: **2 attempted, 2 explicit failures, 0 predictions**.
  This test is a separate fault-injection cohort, not a population failure-rate estimate.
- `npm.cmd run build`: TypeScript and Vite passed; `git diff --check` passed.
- Reliability plot rendered and visually inspected. No independent new-match accuracy claim.
- Fresh saved neural OOF metric reproduction: AP **0.565771**, ROC **0.852616**; still subject
  to the epoch-selection caveat. No new neural fitting performed other than disposable
  synthetic benchmark steps in memory.

Changed production-adjacent files are `run_infer_pipeline.py` (diagnostic persistence),
`cs2cd_adapter.py` and `demoparser2_local.py` (optional participant metadata),
`desktop_result.py` (coverage contract and calibration caveat), and `DesktopApp.tsx`
(coverage display/export). Added `src/utils/player_coverage.py`, the three research scripts,
`ui/api/tests/test_research_validation.py`, and this report. No feature/scoring/model-selection
formula, eligibility threshold or model artifact was changed. No commit/push/deployment made.

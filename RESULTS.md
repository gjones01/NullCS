# Results

This file reports the current public benchmark readout from saved artifacts under `main/data/processed`. It does not invent measurements that are not present in the repository.

## Dataset Summary

### Encounter Model

Source artifact: `main/data/processed/models/encounter_nn_cs2cd_training_manifest.json`

| Item | Value |
| --- | ---: |
| Demos | 894 |
| Encounter windows | 281,792 |
| Positive windows | 30,559 |
| Negative windows | 251,233 |
| Temporal channels | 35 |
| Sequence length | 32 ticks |

### Player-Level Model

Source artifact: `main/data/processed/models/xgb_player_level_cs2cd_eval_summary.json`

| Item | Value |
| --- | ---: |
| Demos after player-count filter | 860 |
| Player-demo rows | 6,886 |
| Positive rows | 992 |
| Negative rows | 5,894 |
| Feature count | 449 |
| Split method | GroupKFold by `demo_id` |

Class balance after filtering is roughly 1 positive row for every 5.94 negative rows. The model uses class weighting during training.

## Model Performance

### Encounter CNN

| Metric | Out-of-fold result |
| --- | ---: |
| PR-AUC | 0.566 |
| ROC-AUC | 0.853 |

The encounter model is useful as a dense behavioral feature generator. Its scores become player-level aggregates rather than final verdicts.

### Player-Level XGBoost

| Metric | Out-of-fold result |
| --- | ---: |
| ROC-AUC | 0.956 |
| PR-AUC | 0.796 |
| Calibrated ROC-AUC | 0.957 |
| Calibrated PR-AUC | 0.791 |

Threshold behavior from the saved evaluation summary:

| Threshold | Precision | Recall | TP | FP | FN | TN |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0.20 | 0.627 | 0.911 | 904 | 537 | 88 | 5,357 |
| 0.30 | 0.673 | 0.883 | 876 | 426 | 116 | 5,468 |
| 0.40 | 0.710 | 0.872 | 865 | 353 | 127 | 5,541 |
| 0.50 | 0.734 | 0.855 | 848 | 307 | 144 | 5,587 |

## Ranking Performance

Source artifact: `main/data/processed/reports/ranked_demo_suspicion_oof_cs2cd.csv`

Among 293 demos labeled with a suspicious player:

| Ranking check | Result |
| --- | ---: |
| Suspicious player ranked top-1 | 92.8% |
| Suspicious player ranked top-2 | 96.2% |
| Suspicious player ranked top-3 | 97.3% |

This is the most relevant readout for review triage. The question is not only whether the classifier separates rows, but whether the player a reviewer should inspect rises near the top of the lobby.

## Behavioral Findings

These are measured observations from the current artifacts.

### 1. Encounter-model scores separate positive and negative player rows

Source artifact: `main/data/processed/reports/ranked_player_demo_suspicion_oof_cs2cd.csv`

- Median `enn_score_mean`: 0.774 for positive rows vs 0.316 for negative rows.
- 87.9% of positive rows are above the negative-row 90th percentile for `enn_score_mean`.
- Median `enn_high_rate`: 0.819 for positive rows vs 0.111 for negative rows.
- 78.4% of positive rows are above the negative-row 95th percentile for `enn_high_rate`.

Interpretation: suspicious rows usually do not rely on one isolated event. They tend to contain clusters of high-scoring encounter windows.

### 2. Window-level CNN scores are elevated on positive windows

Source artifact: `main/data/processed/reports/encounter_nn_cs2cd_oof_encounters.parquet`

- Median encounter CNN score: 0.769 for positive windows vs 0.188 for negative windows.
- 51.5% of positive windows score at or above 0.75, compared with 3.6% of negative windows.
- 35.2% of positive windows score at or above 0.90, compared with 1.2% of negative windows.

Interpretation: the temporal model is finding a repeatable window-level pattern, not only a player-level aggregate artifact.

### 3. Fast-rifle and prefire-like features separate a subset of positives

Source artifact: `main/data/processed/reports/feature_separation_cs2cd.md`

- `prefire_rate_rifle` has feature AUC 0.826; median is 0.500 for positive rows vs 0.111 for negative rows.
- `rifle_fast_rt_rate` has feature AUC 0.811; median is 0.500 for positive rows vs 0.158 for negative rows.
- `headshot_rate` has feature AUC 0.808; median is 0.727 for positive rows vs 0.462 for negative rows.

Interpretation: some suspicious rows are characterized by a combination of fast rifle timing, prefire-like engagements, and high precision. None of these features is sufficient alone.

### 4. Some aim-process features separate by being lower, not higher

Several process features show lower medians for positive rows:

- `enc_preshot_err_std_mean`: median 0.632 for positive rows vs 1.129 for negative rows.
- `enc_snap_jerk_early_mean`: median 0.809 for positive rows vs 0.961 for negative rows.
- `enc_aim_collapse_ratio_high_rate`: median 0.635 for positive rows vs 0.778 for negative rows.

Interpretation: not every suspicious signal is a large snap. Some signals look like cleaner pre-shot stabilization or less noisy correction than expected for the encounter context.

## False Positives And Failure Cases

### Non-cheater demos can still produce high player scores

Source artifact: `main/data/processed/reports/ranked_demo_suspicion_oof_cs2cd.csv`

- Non-cheater demos: 567.
- Median top player score in non-cheater demos: 0.052.
- 90th percentile top player score in non-cheater demos: 0.748.
- Some non-cheater demos reach a max score of 1.000.

The saved player table shows 221 negative player rows from 92 non-cheater demos with risk at or above 0.50. These cases often include high headshot share, fast reaction streaks, through-smoke or prefire-like indicators, and enough kills to provide support.

### Top-1 misses exist

Source artifact: `main/data/processed/reports/top1_misses_cs2cd.csv`

There are 21 labeled-cheater demos where the confirmed suspicious player is not ranked first. In several misses, another player has a materially higher risk score than the labeled suspicious player.

Interpretation: the system can still choose the wrong reviewer starting point inside a suspicious lobby.

### Known hard cases

- **High-skill overlap:** high headshot share, clean reaction timing, and efficient control can resemble suspicious patterns.
- **Low-evidence matches:** players with too few supported engagements can be downweighted or unstable.
- **Wall-only behavior:** if the behavior does not create measurable aim, timing, visibility, or engagement-process anomalies, the current feature set may not separate it reliably.
- **Context gaps:** the model reads demo telemetry, not voice comms, team plans, external information, or multi-match history.

## What Is Not Yet Measured

The repository does not currently contain a validated claim such as "X% of confirmed cheater windows show abnormal crosshair correction patterns." The available artifacts support feature distributions, ranking metrics, and encounter-model score separation. More granular causal labels for specific cheat behaviors should be added before making cheat-type-specific claims.

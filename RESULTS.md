# Results

Measured October 14, 2026. These are internal research results for the new evaluation
pipeline, not accuracy claims for the current desktop installer.

## Dataset and scores

The evaluation scored 6,886 player-match records across 860 of 894 demos.
Source labels contain 992 positive and 5,894 negative scored records.
Some participants lack enough usable evidence to receive a score.

| Output | ROC-AUC | Average precision | Brier score | Log loss |
| --- | ---: | ---: | ---: | ---: |
| Raw model score | 0.957 | 0.797 | 0.0596 | 0.2123 |
| Calibrated output | 0.939 | 0.761 | 0.0548 | 0.5758 |
| Evidence-adjusted review score | 0.939 | 0.764 | 0.0549 | 0.5330 |

ROC-AUC measures score ordering across the labeled classes. Average precision
summarizes precision and recall as the cutoff changes. Neither is an accuracy
percentage. Lower Brier score and log loss are better; log loss penalizes confidently
wrong predictions strongly. Calibration needs work before model release.

## Who appears near the top?

Across all 317 matches with a positive source label, including cases where a player
did not receive a score:

| Review list | Matches with a positively labeled player in that range |
| --- | ---: |
| First place | 270 / 317 (85.2%) |
| Top three | 288 / 317 (90.9%) |
| Top five | 290 / 317 (91.5%) |

Equal scores use player ID order for reproducible reporting. Different tie ordering
would give 265-274, 281-290 and 282-293 matches respectively. Older published results
used a smaller denominator and a different evaluation process; they are not a fair
before/after comparison.

## What these results support

All learned stages exclude the test groups. Known repeated players and overlapping
windows stay together. Historical labels and unknown player identities remain limits.
Raw-score 95% bootstrap intervals were 0.946-0.965 for ROC-AUC and 0.747-0.845 for
average precision (200 group-level resamples). These intervals do not remove label
uncertainty or the effects of earlier development on this dataset.

Read the [research notes](RESEARCH_VALIDATION.md) for the method, release decision
and reproduction commands. The [full results](research/corrected_baseline_summary.json)
contain metrics, counts and run hashes. No new production weights were released.

## Calibration follow-up: October 15

We compared raw scores, sigmoid calibration and isotonic calibration using the
same frozen model predictions. Within each outer fold, three grouped splits of
the calibration data selected the method by log loss. Test scores did not select
the method. All five folds chose sigmoid.

| Output | Log loss (lower is better) | Brier score (lower is better) |
| --- | ---: | ---: |
| Raw scores | 0.2123 | 0.0596 |
| Isotonic calibration | 0.5758 | 0.0548 |
| Selected sigmoid calibration | 0.1948 | 0.0551 |

Sigmoid removed the exact zero/one errors seen with isotonic. It improved log loss
over raw scores in three of five test folds, not every fold. Its pooled average
precision was 0.779, compared with 0.797 for raw scores. Separate calibration
functions can change score ordering between folds even when they preserve it
within each fold. Calibration is not an across-the-board ranking improvement.

At a fixed 0.5 cutoff, before the evidence adjustment:

| Output | Negative-labeled records flagged / 5,894 | Positive-labeled records flagged / 992 |
| --- | ---: | ---: |
| Raw scores | 369 | 857 |
| Isotonic calibration | 185 | 718 |
| Selected sigmoid calibration | 170 | 691 |

Fewer false positives come with more missed positives at this cutoff. These are
source labels, not independently confirmed outcomes. The cutoff was fixed for
comparison; it is not a newly recommended release threshold.

In the professional-demo subset, sigmoid flagged 1 of 982 scored player-match
records at 0.5, versus 35 for raw scores. Those 100 matches contain a large connected
player group and assume legitimate play; this is a useful stress test, not proof
of a real-world false-positive rate.

After the existing evidence adjustment, sigmoid ranked a positively labeled player
first in 270/317 matches and in the top three in 286/317. The previous isotonic
review scores gave 270/317 and 288/317. Ties use player ID order. No thresholds or
ranking rules were changed to improve these results.

Coverage remains 6,886 of 8,857 observed player-match records, across 860 of 894
matches. Missing scores are not counted as correct negative predictions.
The follow-up reused previously inspected tests, so it is continued internal
validation, not a fresh external benchmark. The suspected-player demo was not
used for calibration selection. Production weights and the installer are unchanged.

Full counts, per-fold results and the fixed comparison protocol are in
[calibration results](research/calibration_validation_summary.json).

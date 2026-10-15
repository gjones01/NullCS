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

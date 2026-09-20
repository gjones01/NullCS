# Results

Current public readout, taken from the saved artifacts under `main/data/processed`.
Nothing here is invented: each number is read from a file that is in the repository.

## What was measured

| | Window model | Ranking model |
| --- | ---: | ---: |
| Demos | 894 | 860 |
| Rows | 281,792 windows | 6,886 player rows |
| Positives / negatives | 30,559 / 251,233 | 992 / 5,894 |
| Features | 35 channels x 32 ticks | 449 |
| PR-AUC | 0.566 | 0.796 |
| ROC-AUC | 0.853 | 0.956 |
| Split | out-of-fold | GroupKFold by `demo_id` |

The window model is a feature generator; its scores become player-level summaries
rather than final verdicts.

### Threshold behaviour (ranking model, saved summary)

| Threshold | Precision | Recall |
| ---: | ---: | ---: |
| 0.20 | 0.627 | 0.911 |
| 0.30 | 0.673 | 0.883 |
| 0.40 | 0.710 | 0.872 |
| 0.50 | 0.734 | 0.855 |

## Ranking, which is what review cares about

Across the 293 demos that contain a labelled suspicious player:

| Check | Result |
| --- | ---: |
| Suspicious player ranked #1 | 92.8% |
| Suspicious player ranked #2 | 96.2% |
| Suspicious player ranked #3 | 97.3% |

The useful question is not only "can the model separate rows", but "does the player
a reviewer should open land near the top of that lobby". Most of the time, it does.

## What the data shows

**1. Player scores built from the window model separate the two groups.**
Median `enn_score_mean` is 0.774 for positive rows against 0.316 for negative rows,
and median `enn_high_rate` is 0.819 against 0.111. Suspicious rows tend to contain
clusters of high-scoring windows rather than one isolated event.

**2. The window model itself is doing real work.**
Median window score is 0.769 for positive windows against 0.188 for negative
windows. 35.2% of positive windows score at or above 0.90, against 1.2% of negative
windows.

**3. Fast rifle timing, prefire-like fights and headshots carry part of the signal.**
`prefire_rate_rifle` has a feature AUC of 0.826 (median 0.500 positive vs 0.111
negative), `rifle_fast_rt_rate` 0.811 (0.500 vs 0.158) and `headshot_rate` 0.808
(0.727 vs 0.462). None of them is sufficient on its own.

**4. Some process features separate by being lower, not higher.**
Positive rows show *less* pre-shot aim noise than negative rows
(`enc_preshot_err_std_mean` median 0.632 vs 1.129) and less noisy correction
(`enc_aim_collapse_ratio_high_rate` median 0.635 vs 0.778). Clean stabilisation can
be a signal in its own right.

## Where it gets things wrong

- **Legitimate players can score high.** Among 567 demos with no known cheater, the
  median top player score is 0.052, but the 90th percentile reaches 0.748 and some
  matches top out at 1.000. 221 negative rows from 92 clean demos reach a risk of
  0.50 or more. These are usually high-headshot, fast-reaction games with enough
  kills to support the statistics.
- **The top of the lobby can be wrong.** In 21 labelled-cheater demos the known
  suspicious player is not ranked first, sometimes clearly behind another player.
- **Known hard cases:** very high-skill play that looks efficient; players with too
  few supported fights to be stable; behaviour that leaves no measurable aim,
  timing or visibility trace; and anything outside the demo file, such as comms,
  team plans or multi-match history.

## What is not measured here

The artifacts support feature distributions, ranking metrics and score separation.
They do not support claims like "X% of confirmed cheater windows show a specific
correction pattern". Cheat-type-specific claims need dedicated labels first.

## A note on reproducibility

The saved summary is the reference for the numbers above. Re-running evaluation
today reproduces the ranking closely but not always to the last decimal
(0.793/0.956 rather than 0.796/0.956) with bit-identical inference, which points at
library-version drift rather than a model change. Pinned dependencies are tracked as
open work before any number here is treated as a regression target.
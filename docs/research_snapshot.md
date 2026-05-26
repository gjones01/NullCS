# Research Snapshot

NullCS currently behaves like a match-relative anomaly and review-priority layer. It is not an absolute cheat-probability model.

## Current Status

The project has working components for:

- demo parsing
- engagement-window extraction
- feature engineering
- encounter-level temporal modeling
- player-level aggregation
- gradient-boosted final ranking
- public-safe benchmark reporting

The strongest current story is not that the model can settle cases. It is that suspicious benchmark slices can be raised in review ordering while held-out normal and pro slices remain comparatively quiet.

## Public-Safe Benchmark Read

- suspicious benchmark median / mean top-ranked signal: `0.030 / 0.060`
- normal legit median / mean top-ranked signal: `0.0031 / 0.0037`
- pro stress-test median / mean top-ranked signal: `0.0034 / 0.0040`
- suspicious benchmark top-1 / top-3 retrieval: `0.575 / 0.875`

These values are review signals, not verdict thresholds.

## Modeling Direction

The current direction emphasizes richer temporal encounter representation. Earlier encounter experiments used a smaller channel set. The active direction expands to 35 synchronized channels so the temporal model can see more of the engagement process: aim movement, input behavior, visibility timing, movement state, recoil/settling behavior, and difficulty context.

## What Still Needs Work

- broader validation across varied match sources
- clearer calibration of match-relative scores
- stronger analysis of high-skill false positives
- better documentation of label uncertainty
- continued stress testing against edge cases
- more inspectable per-player explanations

The project should be read as a serious applied ML research effort in progress, not a finished enforcement product.

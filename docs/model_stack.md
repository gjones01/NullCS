# Model Stack

NullCS is built as a staged behavioral modeling pipeline. The stack is intentionally not a single black-box classifier over final match stats.

## 1. Parsed Demo Data

Raw `.dem` files are parsed into structured event and tick tables. Important inputs include kills, shots, damage, rounds, player state, view angles, movement, weapon context, and visibility-derived context where available.

## 2. Engagement Windows

The pipeline extracts short windows around encounters. These windows are the unit of temporal behavior analysis. They preserve what happened before and during a fight rather than reducing the fight to a single outcome.

## 3. Temporal Encounter Channels

Each encounter window is represented as a multi-channel time series. Channels describe synchronized streams such as:

- aim error and aim convergence
- view-angle deltas
- angular velocity and jerk-like movement
- mouse/input movement
- visibility state
- shot and damage timing
- movement state
- scoped, flashed, walking, and airborne context
- low-visibility and difficulty context
- recoil and settling behavior

The current representation has expanded from earlier 12-channel experiments toward a 35-channel encounter representation.

## 4. Encounter Neural Model

The neural encounter model reads the channel-by-time representation and emits encounter-level summaries. It is intended to learn temporal process features that would be difficult to express as simple averages.

Examples include abrupt acquisition, unusually clean settling, input burst patterns, and precision under difficult visibility.

## 5. Player-Level Aggregation

Encounter-level outputs are aggregated into player-demo rows. The aggregation stage includes engineered features and support measures:

- kill and encounter counts
- timing medians and quantiles
- low-visibility rates
- headshot and weapon context
- distance summaries
- round and weapon spread
- top-k encounter model summaries
- confidence/support indicators

## 6. Final Ranking Model

The final ranking model is a gradient-boosted model over player-level rows. It combines conventional features, temporal encounter summaries, and context signals to rank players inside the match.

The output is not a universal probability. It is a match-relative review signal.

## 7. Review Artifacts

The pipeline can produce ranked player tables, reason summaries, evidence tables, and benchmark context. These artifacts are meant to support manual review and technical inspection.

## Why Not End-To-End Only

An end-to-end classifier would be harder to inspect and easier to overstate. The staged design keeps representations separable:

- raw parsed data can be inspected
- encounter windows can be audited
- feature families can be documented
- neural outputs can be aggregated and compared
- final rankings can be evaluated as review ordering

That structure is more appropriate for a research project where interpretability and false-positive discipline matter.

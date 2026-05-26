# Encounter Neural Model

The encounter model is a temporal model over short fight windows. It is designed to learn patterns in synchronized behavior over time rather than relying only on aggregated scalar features.

## Temporal Encounter Windows

A temporal encounter window is a fixed-length slice around an interaction. It can include ticks before visibility, during acquisition, around shots and damage, and after the engagement begins. Each tick contains multiple synchronized streams describing player state and encounter context.

This representation matters because some behavioral differences are visible in timing and shape:

- abrupt target acquisition
- unusually stable post-acquisition behavior
- correction patterns before and after firing
- movement changes before contact
- precision under low visibility
- timing pressure around first visibility or first damage

## Input Tensor

The model input is a tensor shaped conceptually as:

```text
channels x time
```

Each channel is one per-tick stream. A channel can represent aim error, mouse delta, view-angle movement, visibility state, firing state, movement state, damage timing, difficulty context, or another synchronized behavioral signal.

The model reads all channels together across the same time window. That lets it learn relationships between streams, such as whether a view-angle snap coincides with first visibility, whether input becomes unusually quiet after acquisition, or whether precision remains high while visibility is limited.

## From 12 Channels To 35 Channels

Earlier experiments used a smaller 12-channel representation. That was useful for testing whether temporal encounter modeling could add signal, but it was too narrow for the full behavior process.

The current 35-channel direction expands the representation so the model can observe more of the synchronized engagement:

- aim error and aim convergence
- view-angle deltas
- angular velocity and jerk-like movement
- mouse/input movement
- input burst and input stability
- visibility state and visibility transitions
- firing and damage timing
- movement state
- scoped, flashed, walking, and airborne context
- recoil/settling behavior
- difficulty-conditioned precision context
- temporal spacing around relevant events

The point of the expansion is not to make the model more certain. The point is to reduce representational blind spots. If the model only sees a few averages, it cannot learn the difference between two players who end at similar aim positions through different processes.

## What The Temporal Model Can Learn

Averages can summarize what happened. Temporal windows can represent how it happened.

The encounter model is expected to learn patterns such as:

- whether aim convergence is gradual or abrupt
- whether the player over-corrects, under-corrects, or settles unusually cleanly
- whether timing aligns tightly with visibility transitions
- whether input bursts occur before or after target information becomes available
- whether movement state changes the interpretation of timing
- whether precision remains high under difficult visibility or motion context

These outputs are then aggregated. They are not treated as standalone evidence.

## Relationship To The Final Model

The encounter neural model produces encounter-level summaries. Those summaries are folded into player-level aggregation alongside engineered features. The final ranking layer then combines encounter-derived signals with broader player-demo context.

This stacked approach is intentionally conservative: the neural model contributes process-level information, while the final model decides how that information behaves in the larger match-relative profile.

# Temporal CNN Experiments

This repo now includes an encounter-level temporal CNN baseline that scores fight windows and aggregates those scores back to the player level.

## What Changed

- the research stack includes an encounter-level temporal CNN baseline
- the temporal path models short per-encounter sequences before aggregating them back to the player level
- encounter-level scores can be merged back into player features as stacked features for the final player-level model

## Current Status

The temporal CNN path is working and useful for research iteration, but it is not the current champion model. The stronger current public-safe story is:

- stacked encounter modeling matters
- legit hard negatives matter
- benchmark-driven evaluation matters more right now than blind architecture churn

## Why This Model Exists

The player-level model remains the top-level ranking model. The CNN sits underneath it and is intended to capture short temporal control patterns within individual encounters that are hard to preserve in aggregated tabular features alone.

Current structure:

1. Build encounter rows and temporal windows
2. Score each encounter with the temporal CNN
3. Aggregate encounter scores per player in a single demo
4. Merge those stacked features into the player-level model flow

## Public Research Position

The main reason this experiment remains worth documenting publicly is not that it became the top-line champion model. It is that it established two useful research conclusions:

- encounter-level temporal structure carries real signal
- stacking encounter summaries back into the final player-level ranker is more promising than relying on broad aggregates alone

That makes the temporal CNN path valuable research infrastructure even when the final public benchmark story is still told through the broader stacked system.

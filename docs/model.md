# Model Overview

NullCS uses a stacked modeling approach. The intent is to combine temporal encounter modeling with player-level aggregation, while keeping the final output framed as review priority rather than a verdict.

## Data Flow

```text
parsed demo tables
  -> engagement windows
  -> temporal encounter channels
  -> encounter neural model
  -> player-demo feature row
  -> gradient-boosted ranking model
  -> review output
```

## Encounter Layer

The encounter layer reads short temporal windows around fights. Each window is represented as synchronized channels over time. Channels include aim process, view-angle movement, input/control-path features, visibility timing, movement state, firing/damage timing, and difficulty context.

The purpose is to model the shape of behavior around an encounter. It is not treated as standalone evidence.

## Player Aggregation

Encounter outputs are aggregated to player-demo rows. Aggregation includes rates, quantiles, top-k summaries, support counts, low-visibility summaries, difficulty-conditioned summaries, and conventional match context.

This step asks whether unusual patterns persist beyond one isolated moment.

## Final Ranking

The final model is an XGBoost-style gradient boosting layer over player-level features. Its output is used to order players inside the match for review.

The ranking is match-relative. A high score means "inspect sooner," not "the player cheated."

## Why This Stack

The stacked architecture separates two problems:

- the encounter model studies short-window behavioral process
- the final model decides how those process summaries combine with broader player evidence

That separation makes the system easier to inspect than a single opaque end-to-end classifier.

For deeper technical detail, see:

- [Methodology](methodology.html)
- [Feature Engineering](feature_engineering.html)
- [Encounter Neural Model](encounter_model.html)
- [Model Stack](model_stack.html)

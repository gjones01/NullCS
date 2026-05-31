# Methodology

NullCS is built as a post-match behavioral analysis pipeline. The goal is not to classify an account from a single match. The goal is to rank players and encounters that deserve manual review, with enough context to understand why the score moved.

## Data Sources

The current public artifacts combine two kinds of data:

- AWPy/demoparser-derived parsed CS2 demos used by the original player-level pipeline.
- CS2CD benchmark splits with `with_cheater_present` and `no_cheater_present` groups.

Current verified artifacts:

- Encounter-model data: 894 demos and 281,792 encounter windows.
- Player-level grouped evaluation data: 860 demos and 6,886 player-demo rows after the `n_players >= 8` filter.
- Player-level class balance after filtering: 992 positive rows and 5,894 negative rows.

Labels are used for research evaluation. They are not treated as proof that every elevated event is cheating behavior.

## Parse And Event Construction

Raw `.dem` files are parsed into structured tables. The important outputs are:

- tick-level player state;
- kills, damage, shots, grenades, smokes, infernos, bomb events, rounds, and footsteps when available;
- metadata such as map name and demo identifier.

The event builder normalizes these into per-demo artifacts so feature code does not depend on parser-specific table shapes.

## Encounter Windows

An encounter window is a short segment around a player-victim interaction. Windows are designed to capture process:

- what the attacker could see;
- how aim moved before and after visibility;
- whether shots or damage occurred before stable acquisition;
- how movement and distance changed during the window;
- whether mouse/control input became unusually quiet or bursty after acquisition.

The current temporal CNN uses fixed-length sequences with 35 channels.

## Temporal CNN Inputs

The encounter model consumes synchronized per-tick channels:

- aim error and aim-error derivatives;
- mouse delta magnitude and command yaw/pitch deltas;
- command-view gaps;
- distance, attacker speed, and relative speed;
- angular velocity and angular jerk;
- line-of-sight angular velocity and jerk;
- visibility state and visibility transition markers;
- ticks since visibility;
- walking, airborne, scoped, and flashed state;
- shot and damage event indicators;
- ticks to/from nearest shot and damage event.

The CNN is an encounter-level model. It does not produce the final player ranking by itself. Its out-of-fold encounter scores are aggregated into player-demo features such as mean score, top-3 mean, high-score rate, low-visibility score, and kill-end score.

## Player-Level Features

The current CS2CD player-level model uses 449 features. Major groups include:

- kill and support counts;
- reaction-time distribution features;
- headshot, through-smoke, prefire-like, and long-range fast-reaction rates;
- weapon mix and dominant weapon share;
- victim spread and round concentration;
- encounter exposure and visible-ratio distributions;
- time-to-shot and time-to-damage distributions;
- aim-error, aim-acquire, aim-dwell, aim-collapse, and aim-range summaries;
- snap velocity, angular jerk, mouse delta, and post-acquire quietness summaries;
- movement and distance context;
- difficulty-conditioned precision;
- temporal CNN aggregate outputs.

The model excludes identifiers such as SteamID from the feature set.

## Model Stack

The current public stack has two main layers:

1. **Temporal encounter CNN**
   - 35 input channels.
   - Sequence length: 32 ticks.
   - Out-of-fold encounter evaluation: PR-AUC 0.566, ROC-AUC 0.853.

2. **Player-level XGBoost ranking model**
   - 449 features.
   - Grouped by `demo_id` for cross-validation/evaluation.
   - Best public CS2CD configuration uses 800 estimators, max depth 3, learning rate 0.03, and data-dependent class weighting.
   - Out-of-fold player-level evaluation: PR-AUC 0.796, ROC-AUC 0.956.

Calibration is currently isotonic. It improves Brier score and log loss in the saved calibration summary, but calibrated scores are still review signals, not probabilities suitable for enforcement.

## Leakage Controls

Current controls:

- Grouped splits use `demo_id`, preventing rows from the same demo from appearing in both train and validation folds.
- Identifier columns such as `attacker_steamid` and `attacker_name` are excluded from training features.
- CS2CD is used for training/evaluation enrichment; UI upload inference remains a separate parse/inference path.

Known limitation:

- GroupKFold is match-isolated but not chronological. It tests generalization across demos, not future deployment drift.

## Interpretation Rules

NullCS scores should be read as review priority:

- High score: inspect the player and supporting rows first.
- Medium score: check whether the evidence is concentrated or thin.
- Low score: current measured features did not produce a strong review signal.

No single feature or model output is a verdict.

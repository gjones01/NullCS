# NullCS

NullCS is an applied machine learning research project for behavioral review of Counter-Strike demo data.

The project studies whether structured match telemetry can surface review-worthy behavioral anomalies without pretending that a model can produce an enforcement decision. It is not an anti-cheat, not a ban system, and not a verdict engine. The intended framing is analyst triage: rank players and situations that deserve closer inspection, explain what raised the signal, and remain explicit about uncertainty.

Counter-Strike demos are a useful research environment because they contain dense, time-aligned behavioral traces: player state, view angles, input-derived movement, visibility timing, shots, damage, kills, weapon context, and round structure. That makes the problem more interesting than scoreboard classification. The question is not simply whether a player had a high headshot rate. The question is whether the process leading into engagements looks unusual after accounting for match context, visibility, movement, timing, and difficulty.

## Research Question

The central research question is:

> Can post-match demo telemetry be transformed into reliable review-priority signals that surface unusual behavioral patterns while staying quiet on legitimate high-skill play?

That framing matters. A useful system must do more than score suspicious examples highly. It also has to avoid inflating strong legitimate players, high-ELO players, and pro-style stress-test slices. False positives in those groups are especially damaging because they make the output easy to dismiss and reduce trust in any signal the model produces.

## What The System Does

At a high level, NullCS turns one `.dem` file into match-relative review outputs:

1. Parse raw demo data into structured events and tick-level telemetry.
2. Extract engagement windows around player encounters.
3. Derive temporal and contextual behavior features.
4. Run encounter-level temporal modeling over synchronized per-tick channels.
5. Aggregate encounter outputs and engineered features to player-demo rows.
6. Use a final ranking model to order players by review priority inside the match.
7. Export reasons, evidence tables, and benchmark context for manual inspection.

The result is a review queue, not a conclusion. A higher signal means "look here sooner." It does not replace watching the demo, checking round context, or comparing behavior across additional matches.

## What This Project Does Not Claim

NullCS does not claim to:

- identify a specific cheat category such as walling or aim assistance
- determine that an account cheated from a single match
- operate as a live anti-cheat
- support bans or enforcement decisions
- produce a universal probability of cheating
- replace human review of the demo

The project uses suspicious labels and benchmark slices for model development, but public outputs should be read as behavioral triage signals and research artifacts.

## Architecture Overview

The current stack is intentionally layered:

```text
CS demo
  -> parser outputs
  -> event/tick tables
  -> engagement windows
  -> temporal encounter channels
  -> encounter-level neural model
  -> player-level aggregation
  -> gradient-boosted ranking model
  -> analyst-facing review outputs
```

The encounter model is meant to capture short-window behavioral process: how a player moves, aims, reacts, corrects, fires, and transitions through visibility or damage events. The player-level model then combines those encounter summaries with broader match features such as timing distributions, low-visibility outcomes, weapon mix, headshot share, distance, round spread, and support counts.

Detailed documentation:

- [Methodology](docs/methodology.md)
- [Feature Engineering](docs/feature_engineering.md)
- [Encounter Neural Model](docs/encounter_model.md)
- [Model Stack](docs/model_stack.md)
- [Evaluation Philosophy](docs/evaluation.md)
- [Limitations](docs/limitations.md)
- [Research Snapshot](docs/research_snapshot.md)

## Feature Engineering Focus

NullCS is built around behavioral feature design rather than one headline metric. Major feature families include:

- aim process and view-angle deltas
- target acquisition timing
- angular velocity, angular jerk, and snap-like movement
- mouse movement and usercmd-derived control-path signals
- recoil correction and post-shot settling
- movement state, walking, airborne state, scoped state, and flashed context
- visibility-to-shot timing and first-contact windows
- low-visibility precision and occlusion outcomes
- difficulty-conditioned precision
- engagement distance, weapon context, and round context
- temporal spacing such as ticks since previous action and ticks to next action
- collapse rate and collapse ratio around aim convergence
- input burst and input stability

The goal is to describe the process around engagements, not just the result.

## Encounter-Level Neural Modeling

The encounter-level model consumes temporal windows represented as synchronized channels over time. A channel is one per-tick stream: for example mouse movement, view-angle delta, aim error, visibility state, movement state, firing state, damage timing, or difficulty context.

Earlier experiments used a smaller 12-channel representation. The current direction expands that representation to 35 channels so the model can see more of the synchronized engagement process instead of relying on a narrow set of averages. The added channels make it possible to represent timing, control-path behavior, visibility transitions, recoil/settling behavior, and difficulty-conditioned aim process in the same temporal window.

This does not make the model a verdict engine. It only gives the temporal model a richer representation of what happened before, during, and after an encounter.

## Evaluation Philosophy

Standard metrics such as ROC-AUC and PR-AUC are useful, but they are not sufficient for this problem. NullCS is evaluated as a review-priority system, so ranking behavior matters:

- Does the labeled suspicious player appear near the top of the lobby?
- Are normal legitimate demos quiet?
- Are pro and high-skill stress-test slices quiet?
- Does top-3 retrieval improve without creating broad false-positive drift?
- Do elevated scores come with interpretable supporting features?

Top-1 and top-3 retrieval are important because a reviewer needs to know where to look first. Quiet legit/pro behavior is equally important because a system that over-flags strong players is not useful, even if it performs well on obvious suspicious examples.

## Current Public Benchmark Read

Current public-safe benchmark summary:

- suspicious benchmark median / mean top-ranked signal: `0.030 / 0.060`
- normal legit median / mean top-ranked signal: `0.0031 / 0.0037`
- pro stress-test median / mean top-ranked signal: `0.0034 / 0.0040`
- suspicious benchmark top-1 / top-3 retrieval: `0.575 / 0.875`

These values should be read as evidence of review-priority separation, not as cheat probabilities.

## Repository Scope

This repository is the public-safe research side of NullCS:

- methodology and model-stack documentation
- public-safe feature engineering code
- public-safe benchmark summaries and plots
- selected model/evaluation artifacts that are safe to discuss publicly
- supporting documentation for how the research is framed

This repository intentionally avoids shipping:

- raw demos
- private match artifacts
- private uploads
- internal evidence exports
- secrets, tokens, or environment-specific configuration
- generated build artifacts and local release caches

## Acknowledgements

NullCS depends heavily on [`demoparser2`](https://github.com/LaihoE/demoparser), the Counter-Strike demo parsing project maintained by LaihoE and its contributors. Their work makes it practical to turn `.dem` files into structured data that can be studied, tested, and reviewed.

That project has been maintained and improved for years, and NullCS would not be possible in its current form without that foundation.

## License And Redistribution

This public repository does not currently grant an open-source license. The research documentation is public for review, discussion, and transparency, but redistribution of modified builds or repackaged artifacts should not be treated as an official NullCS release.

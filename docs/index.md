# NullCS Research Overview

NullCS is an applied machine learning research project using Counter-Strike demo data as the behavioral environment. The project studies whether post-match telemetry can support analyst triage: surfacing unusual player behavior, ranking review priority inside a match, and explaining which signals contributed to that ranking.

It is not an anti-cheat, not a ban system, and not a verdict engine. The work is closer to behavioral modeling and review support than enforcement automation.

## Research Motivation

Counter-Strike demos contain a dense record of player behavior. They are useful for applied ML because they include time-aligned movement, view angles, shots, damage, visibility, round state, weapon context, and player state. That makes the problem richer than classifying a scoreboard or a video clip.

The research question is whether those traces can be transformed into review-priority signals that are useful without becoming overconfident.

The difficult part is not surfacing obvious abuse. The difficult part is separating unusual behavior from strong legitimate play, especially when the signal is subtle, match-bounded, or sample-limited.

## Current Pipeline

At a high level:

```text
.dem file
  -> parsed event and tick tables
  -> engagement windows
  -> temporal feature channels
  -> encounter-level neural outputs
  -> player-level aggregation
  -> final ranking model
  -> review artifacts
```

The output is match-relative. It is meant to decide who deserves inspection first, not to settle the case.

## Why Match-Relative Review

A strong player can look unusual in a weak lobby. A suspicious player can also avoid obvious headline statistics. For that reason, NullCS ranks behavior inside the current match and exposes support/limitations rather than presenting a universal probability.

This framing keeps the project closer to analyst triage:

- surface unusual behavior
- explain why it was raised
- preserve uncertainty
- keep human review in the loop

## Technical Focus

The strongest parts of the project are the representation and evaluation work:

- structured demo parsing
- engagement-window extraction
- tick-level behavioral features
- usercmd-derived control-path features
- aim convergence and view-angle process features
- visibility timing and low-visibility context
- difficulty-conditioned precision
- encounter-level temporal modeling
- player-level aggregation
- review-oriented retrieval evaluation

## Public Benchmark Read

Current public-safe benchmark summary:

- suspicious benchmark median / mean top-ranked signal: `0.030 / 0.060`
- normal legit median / mean top-ranked signal: `0.0031 / 0.0037`
- pro stress-test median / mean top-ranked signal: `0.0034 / 0.0040`
- suspicious benchmark top-1 / top-3 retrieval: `0.575 / 0.875`

These numbers are not cheat probabilities. They summarize review-priority separation: suspicious benchmark slices should rise near the top of a lobby while normal legit and pro slices remain quiet.

## Recommended Reading

- [Methodology](methodology.html)
- [Feature Engineering](feature_engineering.html)
- [Encounter Neural Model](encounter_model.html)
- [Model Stack](model_stack.html)
- [Evaluation Philosophy](evaluation.html)
- [Limitations](limitations.html)
- [Research Snapshot](research_snapshot.html)

## Boundaries

NullCS does not directly label someone as walling, aim assisting, or using a specific tool. It does not make account-level claims from one match. Its output is a structured prompt for deeper review.

This boundary is not a weakness in the framing. It is the only credible way to discuss this kind of model without overstating what the data can support.

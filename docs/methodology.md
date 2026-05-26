# Methodology

NullCS is organized as a post-match behavioral modeling pipeline. The system is not designed to watch live play or produce enforcement decisions. It takes a recorded Counter-Strike demo, derives structured behavioral signals, and produces match-relative review priorities.

## Pipeline

```text
Raw .dem file
  -> parser tables
  -> canonical events
  -> engagement windows
  -> temporal encounter features
  -> encounter-level neural outputs
  -> player-level aggregation
  -> final ranking model
  -> review artifacts
```

## Demo Parsing

The first stage converts `.dem` files into structured tables. The parser extracts events such as kills, damage, shots, round metadata, and tick-level player state. This matters because the model should not reason from clips or scoreboard summaries. It needs the sequence of what happened and the context in which it happened.

The important distinction is that one match is not one row. A single match becomes many events, many engagement windows, and many per-player aggregates.

## Tick-Level Telemetry

Tick-level telemetry gives the project access to time-aligned behavior:

- player position and movement state
- view angles and aim direction
- shots and damage timing
- weapon state
- visibility and occlusion context
- round and engagement structure
- player state such as scoped, flashed, walking, or airborne

This is the raw material for behavioral modeling. The project is interested in how behavior unfolds over time, not only in final outcomes.

## Engagement Windows

An engagement window is a short slice around a player interaction. Windows are built around moments such as visibility changes, shots, damage, or kills. The goal is to capture the process before, during, and immediately after the fight.

Examples of questions an engagement window can help answer:

- How long was the target visible before the shot?
- Did aim converge smoothly or abruptly?
- Was the player moving, stopped, flashed, scoped, or airborne?
- Did input behavior change around target acquisition?
- Was precision unusually high under low visibility or high difficulty?
- Did the player correct recoil or settle aim in an ordinary way?

## Encounter-Level Modeling

The encounter model reads synchronized per-tick channels inside each window. This temporal representation is useful because many behavioral differences are process-shaped. Averages can hide whether a player acquired a target gradually, snapped into place, over-corrected, corrected recoil, or stayed unusually stable after acquisition.

The encounter output is not used as a standalone claim. It becomes another signal family that is aggregated into the player-level model.

## Player-Level Aggregation

After encounter scoring, the system aggregates evidence to the player-demo level. Aggregation includes:

- counts and support measures
- medians, means, quantiles, and rates
- top-k encounter summaries
- low-visibility and difficulty-conditioned summaries
- timing distributions
- weapon, distance, and round-spread context

This step is where the model moves from individual moments to a player profile inside one match.

## Final Ranking

The final model is a gradient-boosted ranking/classification layer over player-demo rows. Its output is used as a match-relative review priority. This is why the UI and documentation emphasize lobby ordering, top-1/top-3 retrieval, and quiet behavior on legitimate/pro slices rather than a single universal threshold.

## Review Output

The output is meant to support manual analysis:

- ranked players
- signal summaries
- reason cards
- evidence tables
- benchmark context
- limitations and support indicators

The system can help decide where to look first. It cannot decide the case on its own.

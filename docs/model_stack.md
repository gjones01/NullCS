# Model Stack

This document explains the public-safe modeling structure behind NullCS.

## Framing

NullCS is a single-match behavioral review system. It does not try to make a final claim about whether a player is cheating. It tries to identify which players stand out enough inside a match to deserve deeper inspection.

That distinction matters:

- the output is match-relative
- the output is triage-oriented
- the output is designed to be explainable

## Core Modeling Idea

The system looks beyond surface-level outcomes such as kills or headshot rate alone. It studies how behavior unfolds through time and context.

The broad feature families include:

- aim behavior
- target acquisition and shot timing
- movement and fight geometry
- visibility and low-information contexts
- input dynamics
- encounter sequencing

## High-Level Pipeline

The current public-safe model story is a stacked review pipeline:

1. Tick-level demo data is parsed into structured match events.
2. Encounter-level and player-level features are built from those events.
3. Encounter-level modeling produces additional stacked signals.
4. A player-level model consumes both direct features and stacked encounter summaries.
5. Players are ranked relative to others in the same match.

The ranking is then used as a review-priority signal.

## Why Match-Relative Ranking

A strong legitimate player can look unusual in a weak lobby. A modest cheater can try to hide behind ordinary-looking headline stats. Because of that, the more useful question is often:

`Who stands out most in this match, and why?`

That is a better fit for behavioral triage than pretending the model can produce a clean universal verdict from one score.

## Player-Level Features

The player-level side summarizes how behavior looks across the match for one player. In public-safe terms, these features are meant to capture:

- reaction-like timing behavior
- prefire-like patterns
- distribution of engagement distances
- difficulty-conditioned precision
- concentration or spread of suspicious-looking moments

These are not treated as verdict features in isolation. They are used together and interpreted relative to the rest of the lobby.

## Encounter-Level Features

The encounter-level side tries to preserve structure that would be lost if everything were flattened too early.

Examples of what encounter modeling is trying to represent:

- how aim settles after visibility begins
- whether difficult fights retain unusually clean control
- whether suspicious-looking moments cluster in low-visibility or high-pressure contexts
- whether the strongest anomalies are narrow or broad across encounter types

This part of the stack matters because many interesting behaviors are sequence-shaped, not just column-shaped.

## Stacked Encounter Signals

One of the more important research directions in NullCS has been stacking encounter-level information back into the final player-level ranking model.

That means:

- encounter-level models score or summarize individual fights
- those outputs are aggregated per player
- the aggregated encounter summaries become additional player-level inputs

This has been more useful than relying on broad player aggregates alone.

## Temporal CNN Work

The repo also includes encounter-level temporal CNN experimentation.

The practical conclusion so far is:

- temporal modeling is useful
- encounter stacking is a worthwhile direction
- the temporal CNN branch is not the current public-facing champion by itself


## What The Model Is Trying To Optimize

The system is most useful when it does two things well at the same time:

- surfaces suspicious benchmark cases near the top of the lobby
- stays quiet on strong legitimate and pro-level stress-test slices


## What The Model Is Not

NullCS is not:

- a ban system
- a client anti-cheat
- a kernel or memory scanner
- a one-score proof of cheating

It is a behavioral review system built around explainable match-relative ranking.


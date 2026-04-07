# Benchmark Methodology

This document explains the public-safe benchmark framing used in the repo.

## Why The Benchmark Is Simple

The benchmark is intentionally framed in a way that is easy to defend publicly.

The main question is not:

`Can one score prove that a player is cheating?`

The main question is:

`Does the system surface suspicious benchmark cases clearly while staying quiet on strong legitimate play?`

That is the more honest evaluation target for a behavioral review system.

## Benchmark Slices

The public-safe benchmark story is built from three slice types:

- suspicious benchmark
- normal legit
- pro stress-test

Each slice serves a different purpose.

### Suspicious benchmark

This slice answers:

- does the system surface the kinds of cases it is meant to raise?
- do suspicious benchmark matches rise clearly at the top of the lobby?

### Normal legit

This slice answers:

- does ordinary legitimate play stay quiet?
- does the system avoid inflating low-risk matches?

### Pro stress-test

This slice answers:

- does the system remain restrained on very strong legitimate players?
- is the model overreacting to high-skill mechanics alone?


## Why This Matters

A system that only raises suspicious cases but also lights up strong legitimate players is not useful enough. The more interesting result is when:

- suspicious slices still surface clearly
- legit and pro slices remain quiet

That shape is stronger evidence of a meaningful behavioral signal than a louder but sloppier model.

## Public-Safe Summary Metrics

The public repo focuses on simple, interpretable summaries such as:

- median top-ranked signal
- mean top-ranked signal
- high-level slice comparison plots
- broad top-of-lobby retrieval summaries

These summaries are enough to communicate the project direction without exposing private data, model artifacts, or sensitive operational details.

## Why Match-Relative Signals

NullCS produces match-relative triage outputs.

That means:

- a higher signal does not mean proof
- a lower signal does not mean innocence
- the signal is best read as review priority inside the current match



## Why Lower Legit Values Are Good

For the legit and pro slices, lower top-ranked signals are desirable which has showed up in testing.

That does not mean the system is weak. It means the model is less likely to overstate strong legitimate play. In practice, that is one of the most important signs of a healthier review system.

## What This Repo Avoids Showing

The public repo does not expose:

- raw demo files
- per-player private evidence exports
- Steam IDs
- model binaries
- private local artifacts
- operational thresholds tied to enforcement claims

The benchmark is therefore meant to communicate research direction and behavioral separation, not an enforcement-ready product claim.

## Interpretation Guidance

The benchmark should be read like this:

- suspicious benchmark slices should be visually and numerically louder
- legit and pro slices should stay visually and numerically quiet
- the project is strongest when both are true at once




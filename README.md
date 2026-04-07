# NullCS

NullCS is a machine learning research project for behavioral review in Counter-Strike demos.

The project studies whether suspicious behavior can be surfaced from tick-level demo data in a way that is measurable, explainable, and conservative around false positives. The system is built for match-relative triage and analyst review, not automated enforcement or one-click verdicts.

## Start Here

If you are visiting the repo for the first time, read these in order:

1. `docs/research_snapshot.md`
   High-level benchmark story, current findings, and public-safe plots
2. `docs/model_stack.md`
   What the modeling pipeline is actually trying to do
3. `docs/benchmark_methodology.md`
   How to interpret the benchmark slices and why quiet legit/pro behavior matters
4. `docs/public_repo_scope.md`
   What this public repo includes and what stays private

## What This Public Repo Covers

This repo is the public-safe research side of NullCS:

- feature engineering for player-level and encounter-level behavioral signals
- stacked modeling experiments for match-relative player ranking
- benchmark methodology and public-safe benchmark summaries
- selected plots, charts, and written findings

This repo intentionally avoids shipping:

- raw demos and private match artifacts
- processed local artifacts and private datasets
- model binaries and internal evidence exports
- local product packaging and private operational codepaths

## Current Public-Safe Read

The strongest current high-level benchmark story is:

- suspicious benchmark cases surface clearly at the top of the lobby
- held-out normal legit demos stay very quiet
- pro stress-test demos also stay quiet

Public-safe benchmark summary:

- suspicious benchmark median / mean top-ranked signal: `0.748 / 0.654`
- normal legit median / mean top-ranked signal: `0.0073 / 0.0093`
- pro stress-test median / mean top-ranked signal: `0.0073 / 0.0074`
- suspicious benchmark top-1 / top-3 retrieval: `0.60 / 0.90`

That is the shape you want from a behavioral review system. The goal is not to call someone a cheater from one score. The goal is to surface the players who deserve deeper review while minimizing false positives on strong legitimate players.

See:

- `docs/research_snapshot.md`
- `docs/benchmark_methodology.md`

## What To Look At

If you want the shortest useful summary of the project:

- look at the benchmark slice plots in `docs/research_snapshot.md`
- read the stacked-model overview in `docs/model_stack.md`
- read `docs/public_repo_scope.md` to understand what is intentionally omitted from the public repo

## Research Direction

NullCS currently centers on a stacked review pipeline:

1. parse tick-level demo data
2. build encounter-level and player-level behavioral features
3. score players with a match-relative ranking model
4. study where suspicious cases separate from held-out legit and pro slices

The project has also explored encounter-level temporal modeling, including a temporal CNN path. That line remains useful research infrastructure, but the main public story is still the benchmark behavior of the broader stacked review system.

See:

- `docs/model_stack.md`
- `docs/cnn_experiments.md`

## Repo Guide

- `docs/research_snapshot.md`
  Public-safe benchmark summary and current findings

- `docs/model_stack.md`
  End-to-end explanation of the modeling approach

- `docs/benchmark_methodology.md`
  How the benchmark slices and metrics are framed

- `docs/cnn_experiments.md`
  Encounter-level temporal modeling notes

- `docs/public_repo_scope.md`
  What is intentionally public here and what is kept private

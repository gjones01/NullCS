# Benchmark Methodology

The benchmark framing is designed around review triage, not enforcement.

The main question is:

> Does the system rank review-worthy suspicious benchmark players near the top while staying quiet on legitimate and pro-style holdouts?

The main question is not:

> Can one score prove that a player cheated?

## Benchmark Groups

The public benchmark read uses three broad groups:

- suspicious benchmark slices
- held-out normal legitimate slices
- pro or high-skill stress-test slices

The third group is important. A system that works only by flagging strong mechanical play will fail when tested against high-skill legitimate players.

## Review-Oriented Metrics

The project uses standard ML metrics where useful, but the practical evaluation emphasizes review ordering:

- top-ranked signal
- top-1 retrieval
- top-3 retrieval
- quietness on legit/pro slices
- support level and reason quality

Top-3 retrieval matters because NullCS is not a one-click decision tool. If the right player is consistently near the top of the review queue, the system can still be useful even when top-1 is imperfect.

## Reading The Public Numbers

Current public-safe summary:

- suspicious benchmark median / mean top-ranked signal: `0.030 / 0.060`
- normal legit median / mean top-ranked signal: `0.0031 / 0.0037`
- pro stress-test median / mean top-ranked signal: `0.0034 / 0.0040`
- suspicious benchmark top-1 / top-3 retrieval: `0.575 / 0.875`

These numbers should be interpreted as ranking behavior, not cheat probabilities.

## Failure Modes The Benchmark Should Catch

A credible benchmark should expose:

- broad false-positive drift on legitimate players
- inflation of pro or high-skill demos
- models that only work on obvious cases
- high scores without stable support
- overreliance on one metric family

The benchmark is strongest when suspicious slices rise while legitimate and pro slices remain quiet.

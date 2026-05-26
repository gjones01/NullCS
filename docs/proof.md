# Benchmarks

This page keeps the older `proof.html` URL working, but the framing is benchmarks rather than proof. NullCS does not use one plot or one score as proof that a player cheated.

## Current Public-Safe Benchmark Summary

- suspicious benchmark median / mean top-ranked signal: `0.030 / 0.060`
- normal legit median / mean top-ranked signal: `0.0031 / 0.0037`
- pro stress-test median / mean top-ranked signal: `0.0034 / 0.0040`
- suspicious benchmark top-1 / top-3 retrieval: `0.575 / 0.875`

The intended read is review-priority separation. Suspicious benchmark slices should surface near the top of the lobby, while normal legit and pro slices should remain quiet.

## Why This Matters

For this project, the strongest evidence is not a single high score. The stronger pattern is:

1. suspicious benchmark cases rise in the review order
2. normal legitimate cases do not broadly inflate
3. pro or high-skill stress-test cases remain quiet
4. the raised cases have inspectable supporting signals

## Benchmark Figures

![Benchmark slice comparison](assets/plots/benchmark_slice_signals.png)

![Suspicious player retrieval summary](assets/plots/cheater_retrieval_summary.png)

![Top-1 distribution](assets/site_proof/benchmark_top1_distribution.png)

![Top-1 vs top-3 scatter](assets/site_proof/benchmark_top1_vs_top3_scatter.png)

## Interpretation

These figures are not enforcement claims. They are evidence that the current representation and ranking approach can create useful review ordering under public-safe benchmark slices.

For the evaluation framing, see [Evaluation Philosophy](evaluation.html).

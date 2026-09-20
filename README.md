# NullCS

NullCS reads Counter-Strike 2 demo files and turns them into a ranked list of
players worth a human look, together with the measurements that pushed each score
up.

It is **not** an anti-cheat, **not** a ban system and **not** an automatic verdict.
A high score means "look here first". Nothing more.

## The question

Scoreboard numbers are too coarse. A high headshot rate or a very short reaction
time can be meaningful, but skill, weapon choice, angle, visibility and round
context all move those numbers too. NullCS asks a narrower question:

> Can tick-level demo data surface unusual behaviour for review, while staying
> quiet on legitimate high-skill play?

## How it works

```text
CS2 .dem file
  -> per-tick parse tables
  -> short windows around each engagement
  -> window model (what aim, mouse and visibility did before the shot)
  -> per-player match features (~450 numbers per player)
  -> ranking model
  -> ranked players plus the evidence rows behind each score
```

Two models, deliberately separate:

1. **Window model (CNN).** Reads short tick sequences around a fight: aim error,
   mouse movement, view/command gaps, visibility, movement, shot timing. It scores
   windows, never players.
2. **Ranking model (XGBoost).** Uses ~450 per-player numbers, including summaries
   of the window scores, to rank the players inside one demo.

## Current benchmark

Read from the saved evaluation artifacts (see [RESULTS.md](RESULTS.md)):

| Metric | Value |
| --- | ---: |
| Demos evaluated | 860 |
| Player rows (992 positive / 5,894 negative) | 6,886 |
| ROC-AUC | 0.956 |
| PR-AUC | 0.796 |
| Suspicious player ranked #1 in the lobby | 92.8% |
| Suspicious player ranked top-3 | 97.3% |

These are review-ranking numbers, not enforcement numbers.

## What it tends to find

- Suspicious rows rarely hinge on one event. They show clusters of high-scoring
  engagement windows.
- Fast rifle timing, prefire-like fights and headshot concentration separate some
  positive rows from the baseline.
- Some non-cheater matches still score high, usually high-headshot, fast-reaction
  games. That is expected, and it is only useful if it stays visible and checkable.

## Documentation

- [METHODOLOGY.md](METHODOLOGY.md) - how the data and models are built, in plain language.
- [RESULTS.md](RESULTS.md) - current numbers, what they mean, where it fails.
- [PIPELINE.md](PIPELINE.md) - commands to rebuild everything and where files land.

## Scope

This repository holds research code, documentation and the public site. It does not
ship raw demos, private match data, secrets or enforcement tooling.

## Credits and licence

Built on [`demoparser2`](https://github.com/LaihoE/demoparser) by LaihoE and
contributors. No open-source licence is granted; the documentation is public for
review and transparency.
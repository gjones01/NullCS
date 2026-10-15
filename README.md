# NullCS

## Community desktop beta

Download the Windows x64 installer from [GitHub Releases](https://github.com/gjones01/NullCS/releases). This beta is unsigned; Windows may show an unknown-publisher warning. Do not disable security protections. Automatic updates are not configured yet: check Releases for new versions.

Analyze a local CS2 `.dem` up to 1 GiB, review the ranked players, and save a plain-text report. Processing stays on your computer. Scores are research signals, not cheating verdicts. Read [release/setup requirements](DESKTOP_RELEASE.md) and [attributions](NOTICE.md).

Original NullCS code and original model artifacts are GPL-3.0-only; third-party materials retain their own licenses. See [LICENSE](LICENSE). Contributions submitted for inclusion must be available under this license; contributors retain their copyrights.

To build the desktop app, use Windows x64/Python 3.13, install `main/ui/web/scripts/requirements-desktop.lock.txt` in a fresh environment, and set `NULLCS_RELEASE_PYTHON` to its Python executable. Download the matching `nullcs-model-artifacts.zip` release asset, verify it against `SHA256SUMS.txt`, and extract its contents into `main/data/processed/models/`. Install the web dependencies with `npm ci` in `main/ui/web`, then run `npm run desktop:build`. The installer does not require an installed Python runtime. Building also requires Rust and the Windows desktop build tools documented in DESKTOP_RELEASE.md.

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

The October 2026 internal evaluation scored 6,886 player-match records across 860
matches. Raw model scores reached **0.957 ROC-AUC** and **0.797 average precision**.
A positively labeled player ranked first in 270 of 317 positive-label matches
(85.2%), and in the top three in 288 (90.9%).

These results describe the new research pipeline, not the existing installer.
Calibration still needs work before replacement weights can be released.
Read [results](RESULTS.md) and [research notes](RESEARCH_VALIDATION.md) for the
method, limitations and reproduction steps.

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
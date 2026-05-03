# NullCS

NullCS is a machine learning project for behavioral review in Counter-Strike demos.

The project studies whether suspicious behavior can be surfaced from tick-level demo data in a way that is measurable, explainable, and conservative around false positives. The current product direction is a local desktop review app for `.dem` files, not a live anti-cheat or automated ban system.

## Desktop Beta

The usable entrypoint is now the NullCS desktop app:

1. Open the desktop app.
2. Drop in one Counter-Strike `.dem` file.
3. Run local analysis.
4. Review the ranked Players tab.
5. Inspect reports for players that need deeper review.

The desktop app accepts `.dem` files only. It does not analyze videos, screenshots, scoreboard images, or live matches.

The beta installer should be distributed through GitHub Releases, not committed directly to the repository. The current Windows installer is built locally at:

```text
main/ui/web/src-tauri/target/release/bundle/nsis/NullCS_0.1.0-alpha.1_x64-setup.exe
```

That file is intentionally ignored because it is a large release artifact. Upload it as a release asset when publishing a beta.

## Project Site

This repo has a GitHub Pages-ready project page in `docs/`.

To publish it:

1. Open the repo on GitHub.
2. Go to `Settings -> Pages`.
3. Choose `Deploy from a branch`.
4. Select `main`.
5. Select `/docs`.

The landing page source is `docs/index.md`.

## Start Here

If you are visiting the repo for the first time, read these in order:

1. `docs/index.md`
   Public landing page, desktop beta direction, and benchmark summary
2. `docs/proof.md`
   Short proof and benchmark story
3. `docs/model.md`
   Public-safe model and pipeline overview
4. `docs/benchmark_methodology.md`
   How to interpret the benchmark slices and why quiet legit/pro behavior matters
5. `docs/scope.md`
   What this public repo includes and what stays private

## Current Public-Safe Read

The strongest current high-level benchmark story is:

- suspicious benchmark cases surface clearly at the top of the lobby
- held-out normal legit demos stay very quiet
- pro stress-test demos also stay quiet

Public-safe benchmark summary:

- suspicious benchmark median / mean top-ranked signal: `0.030 / 0.060`
- normal legit median / mean top-ranked signal: `0.0031 / 0.0037`
- pro stress-test median / mean top-ranked signal: `0.0034 / 0.0040`
- suspicious benchmark top-1 / top-3 retrieval: `0.575 / 0.875`

In plain English, the benchmark is checking whether NullCS puts suspicious benchmark players near the front of the review queue while staying quiet on normal legitimate and pro demos. Top-3 retrieval matters because this is a review tool: the goal is to decide who deserves inspection first, not to let one score replace human review.

## Public Repo Scope

This repo is the public-safe side of NullCS:

- desktop beta source for the local review app
- feature engineering and model-pipeline source that is safe to publish
- benchmark methodology and public-safe benchmark summaries
- selected plots, charts, and written findings

This repo intentionally avoids shipping:

- raw demos and private match artifacts
- processed local artifacts and private datasets
- private uploads and internal evidence exports
- generated build outputs, installer binaries, and local caches
- secrets, tokens, and environment-specific config

## Release Notes

The installer belongs in GitHub Releases. GitHub blocks normal Git files over 100 MB, and the current installer is roughly 320 MB. Commit source and documentation to Git; upload the `.exe` as a release asset.

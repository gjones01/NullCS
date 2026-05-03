# NullCS

NullCS is a machine learning project for behavioral review in Counter-Strike demos.

The project studies whether suspicious behavior can be surfaced from tick-level demo data in a way that is measurable, explainable, and conservative around false positives. The current product direction is a local desktop review app for `.dem` files, not a live anti-cheat or automated ban system.

## Download The Beta

For normal users, the intended path is the Windows desktop installer from GitHub Releases:

- Releases: `https://github.com/gjones01/NullCS.ai/releases`
- Current installer asset name: `NullCS_0.1.0-alpha.1_x64-setup.exe`

Install it, open NullCS, and run a local demo review:

1. Open the desktop app.
2. Drop in one Counter-Strike `.dem` file.
3. Run local analysis.
4. Review the ranked Players tab.
5. Inspect reports for players that need deeper review.

NullCS runs locally on your PC. Demo files are not uploaded to a cloud service by the desktop app.

The desktop app accepts `.dem` files only. It does not analyze videos, screenshots, scoreboard images, or live matches. A player landing in Review means the demo deserves closer inspection; it does not mean a single match should be treated as the whole case.

## Expected Runtime

Inference time depends on demo size, round count, disk speed, CPU, and whether Windows Defender or other security tools scan the demo while it is being processed.

Maintainer baseline:

- CPU: Intel i5-13400F
- GPU: NVIDIA RTX 3060 Ti
- Memory: 32 GB DDR5
- Platform: Windows desktop build, local inference

Measured local run:

| Demo size | Pipeline path | Time |
| --- | --- | ---: |
| 143.3 MiB `.dem` | parse + feature build + encounter NN features + XGBoost scoring + report output | 25.2 seconds |

As a rough expectation, normal match demos should usually complete in under a few minutes on a similar desktop. Very large demos, slower CPUs, slower disks, or first-run security scanning can push that higher.

## Build From Source

Most users should use the release installer. Source builds are for contributors or anyone who wants to inspect and build the app locally.

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

## Acknowledgements

NullCS depends heavily on [`demoparser2`](https://github.com/LaihoE/demoparser), the Counter-Strike demo parsing project maintained by LaihoE and its contributors. Their work makes it practical to turn `.dem` files into structured data that can be studied, tested, and reviewed.

That project has been maintained and improved for years, and NullCS would not be possible in its current form without that foundation. Thank you to the `demoparser2` maintainers and contributors for keeping that ecosystem moving.

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

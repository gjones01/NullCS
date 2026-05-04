# NullCS

NullCS is a local desktop beta for behavioral review of Counter-Strike demo files.

It uses structured `.dem` data, feature engineering, and machine learning models to rank match-relative behavioral standouts for manual review. It is a research and analyst-triage tool, not a live anti-cheat, ban system, or one-click verdict engine.

## Download The Beta

Normal users should install the Windows desktop beta from GitHub Releases:

- Releases: `https://github.com/gjones01/NullCS.ai/releases`
- Current installer asset: `NullCS_0.1.0-alpha.1_x64-setup.exe`

Basic flow:

1. Install and open NullCS.
2. Choose or drop in one Counter-Strike `.dem` file.
3. Run local analysis.
4. Review the ranked Players tab.
5. Open a player report when a player deserves closer inspection.

The desktop app runs locally on your PC. The beta desktop workflow does not upload demo files to a cloud service.

## Accepted Input

NullCS accepts Counter-Strike demo files ending in `.dem`.

It does not analyze:

- videos or clips
- screenshots
- scoreboard images
- ZIP/RAR archives
- live matches
- account history outside the loaded demo

Each run analyzes one match and ranks players inside that match only.

## How To Read Output

NullCS is a review queue. A higher signal means "look here sooner", not "this case is settled."

Common terms:

- **Signal**: how far a player stands out relative to the current match.
- **Support**: how much usable evidence exists for that player in the loaded demo.
- **Typical**: within the expected range for the current match.
- **Watch**: unusual enough to keep in view, but not suspicious by itself.
- **Review**: signals are starting to align with irregular play patterns and should be checked with round context, POV, and supporting evidence.
- **Strong**: numerous signals are elevated at once and the case should be reviewed before lower-priority players.

Edge cases should be checked against the actual demo, round context, opponent behavior, teammate information, and ideally other matches from the same player.

## What This Project Does Not Claim

NullCS does not claim to be:

- a live anti-cheat
- a ban or enforcement system
- a conclusion from a single score
- a detector for any single cheat category
- a replacement for watching the demo and reviewing context
- a system that can make account-level claims from one match

The goal is to make suspicious or unusual behavioral patterns easier to inspect, while staying honest about uncertainty and false-positive risk.

## Expected Runtime

Runtime depends on demo size, round count, disk speed, CPU, and whether Windows Defender or another security tool scans files during processing.

Maintainer baseline:

| Machine | Demo size | Pipeline path | Time |
| --- | ---: | --- | ---: |
| Intel i5-13400F, RTX 3060 Ti, 32 GB DDR5 | 143.3 MiB | parse + feature build + encounter NN features + XGBoost scoring + report output | 25.2 seconds |

On a similar desktop, normal match demos should usually complete in under a few minutes. Very large demos, slower CPUs, slower disks, or first-run security scanning can take longer.

## Known Limitations

- This is a public beta. Wording, thresholds, and UI layout may change between builds.
- Results are match-relative, not a long-term player reputation score.
- Single-demo reads can be noisy, especially with small samples or unusual match context.
- Strong legitimate players can produce isolated elevated signals.
- The installer is currently unsigned, so Windows may warn on first install.
- The app is Windows-focused for the current beta.
- Large demos may take several minutes to parse.
- Some reports may have thinner evidence if the demo has limited usable encounters for a player.

## Bugs And Feedback

When reporting an issue, include:

- Windows version
- NullCS release version
- whether the app froze, errored, or produced confusing output
- approximate demo size
- what step failed: intake, parsing, feature build, model, report, or external profile links
- a screenshot of the error message if one appears

Do not upload private demos publicly unless you are comfortable sharing them. For public GitHub issues, describe the failure without attaching sensitive match data.

## Build From Source

Most users should use the release installer. Source builds are for contributors or technical users who want to inspect and build the app locally.

The installer is intentionally distributed through GitHub Releases, not committed to the repository, because it is a large build artifact.

Local installer path after a release build:

```text
main/ui/web/src-tauri/target/release/bundle/nsis/NullCS_0.1.0-alpha.1_x64-setup.exe
```

## Project Site And Docs

- Public site: `https://www.nullcs.app`
- Site source: `main/ui/site`
- Static docs: `docs/index.md`

Start with:

1. `docs/index.md` - public overview and benchmark summary
2. `docs/proof.md` - benchmark story
3. `docs/model.md` - public-safe model and pipeline overview
4. `docs/benchmark_methodology.md` - how to interpret benchmark slices
5. `docs/scope.md` - what the public repo includes and omits

## Current Public-Safe Benchmark Read

The current public benchmark story is:

- suspicious benchmark cases surface more often near the top of the lobby
- held-out normal legit demos stay quiet
- pro stress-test demos also stay quiet

Summary values:

- suspicious benchmark median / mean top-ranked signal: `0.030 / 0.060`
- normal legit median / mean top-ranked signal: `0.0031 / 0.0037`
- pro stress-test median / mean top-ranked signal: `0.0034 / 0.0040`
- suspicious benchmark top-1 / top-3 retrieval: `0.575 / 0.875`

Top-3 retrieval matters because this is a review tool. The goal is to decide who deserves inspection first, not to let one score replace human review.

## Acknowledgements

NullCS depends heavily on [`demoparser2`](https://github.com/LaihoE/demoparser), the Counter-Strike demo parsing project maintained by LaihoE and its contributors. Their work makes it practical to turn `.dem` files into structured data that can be studied, tested, and reviewed.

That project has been maintained and improved for years, and NullCS would not be possible in its current form without that foundation. Thank you to the `demoparser2` maintainers and contributors for keeping that ecosystem moving.

## Public Repo Scope

This repo is the public-safe side of NullCS:

- desktop beta source for the local review app
- public-safe feature engineering and model-pipeline source
- benchmark methodology and public-safe benchmark summaries
- selected plots, charts, and written findings

This repo intentionally avoids shipping:

- raw demos and private match artifacts
- processed local artifacts and private datasets
- private uploads and internal evidence exports
- generated build outputs, installer binaries, and local caches
- secrets, tokens, and environment-specific config

---
title: NullCS
---

# NullCS

NullCS is a machine learning project for behavioral review in Counter-Strike demos.

At a high level, the project studies whether suspicious behavior can be surfaced from tick-level demo data in a way that stays measurable, explainable, and conservative around false positives. The current purpose is to surface instances of irregular play that deserve further review and provide supporting evidence for manual inspection.

[View the GitHub repository](../)<br>
[Proof](proof.html)<br>
[Model](model.html)<br>
[Desktop beta](https://github.com/gjones01/NullCS.ai/releases)

## Project Overview

NullCS combines structured demo parsing, encounter-level feature engineering, player-level aggregation, and match-relative ranking. The point is to turn a messy demo into a ranked review queue with supporting evidence, so the most irregular players can be inspected first.

### What the current stack does

1. Parse a Counter-Strike demo into structured match data.
2. Build encounter-level and player-level behavioral features.
3. Score players with a match-relative ranking model.
4. Export evidence-oriented outputs that can be inspected more closely.


## Why I Built This

NullCS originally stemmed from a chronic occurrence of running into rage cheaters. Everything from spinbots to inhuman aimbots. The more interesting cases, though, were players who were trying to hide it. The obvious cases are frustrating, but the closet-cheating problem is harder because the behavior is mixed into otherwise normal-looking gameplay. For context, I am not a highly skilled player grinding Premier or FaceIt each day. I am a very casual player with most matches in competitive with friends and the occasional Premier sessions. I am someone who simply loves Counter-Strike and saw this as an opportunity to apply something I am passionate about, to a game I enjoy to play.

I did not start this as an attempt to build an "anti-cheat" or compete with any other ecosystems. I wanted to study whether unfair gameplay could still be surfaced from demo data when the behavior was not blatant. As of April 2026, VAC has improved slightly at stopping pure rage cheating, particularly spinbots, but wallhacks, aim assist, and recoil assistance are still meaningful problems in regular matches.

That made the project a useful technical challenge: take something messy and subjective, turn it into structured data, and see how far careful measurement could go without pretending the model had more certainty than it actually did. NullCS does not run live during matches; it relies on `.dem` files for post-game analysis. Therefore, by definition, it is not an "anti-cheat" in the traditional sense.

## Personal Framing

NullCS became my way of learning data science, machine learning, and deployment through a problem I actually cared about. Instead of working through only clean tutorial datasets, I wanted to deal with something that was unintuitive and noisy.

The project also forced me to think beyond "does the model score high?" A useful review tool needs to be conservative and honest about uncertainty. It is not perfect and does not claim to detect every type of irregular gameplay. That shaped the way I approached the work. The goal became less about producing a dramatic detection number and more about building a system that can point to evidence, show its reasoning, and stay quiet when the signal is weak.

## What I Learned

The biggest lesson was that feature engineering and data quality matter more than model choice. The model can only learn from the structure it is given, so a lot of the real work was in defining encounters, measuring timing, handling visibility, aggregating player behavior, and avoiding leakage between training and evaluation.

I also learned how fragile labels can be. A suspicious demo is not the same thing as a cleanly labeled player, and a missing or incorrect SteamID can change the meaning of an entire training row. That pushed the project toward grouped validation, conservative reporting, and review-oriented outputs instead of binary claims.

Obviously technical skills were gained or built upon more, such as 1-D CNNs, gradient boosting models, feature engineering, weighting, thresholds etc. However, the most valuable skill I gained was research. Counter-Strike cheat documentation is fairly niche, definitions are unofficial with meanings changing between communities once you pass surface level terms. It required me to understand how Counter-Strike 2, as a video game, worked inside of the Source2 engine. Much time was spent understanding how viewangle logic behaves, the significance of the "user_cmd", or the fact that the eye height of the character is 64 units (which was crucial for building logic on what the player is looking at). I learned that it's not about knowing everything, but rather knowing where to look when you don't understand. This did include me joining "cheater communities" to witness what they talked about and how they avoid detection.


## Current Benchmark Read

The public-safe benchmark story is intentionally simple: NullCS should raise suspicious benchmark demos more often than ordinary legit demos, while staying quiet on strong legitimate play.

- suspicious benchmark cases should appear near the top of the lobby
- held-out normal legit demos should stay very low
- pro stress-test demos should also stay very low

Current public-safe summary values:

- suspicious benchmark median / mean top-ranked signal: `0.030 / 0.060`
- normal legit median / mean top-ranked signal: `0.0031 / 0.0037`
- pro stress-test median / mean top-ranked signal: `0.0034 / 0.0040`
- suspicious benchmark top-1 / top-3 retrieval: `0.575 / 0.875`

In plain English:

- **Suspicious benchmark median / mean top-ranked signal** means the typical and average highest player score inside known suspicious benchmark demos. Higher is expected here because those demos are supposed to contain stronger irregular behavior.
- **Normal legit median / mean top-ranked signal** means the same measurement on ordinary held-out legitimate demos. Lower is better because the tool should avoid overreacting to normal players.
- **Pro stress-test median / mean top-ranked signal** checks whether high-skill play gets over-flagged. These values staying near the normal legit slice is important because strong aim alone should not trigger the system.
- **Top-1 / top-3 retrieval** means how often the known suspicious player was ranked first, or at least within the top three players to review. Top three matters because the desktop app is a review queue: it is meant to decide who should be inspected first, not automatically decide the case.

These are review signals, not verdict thresholds. A higher score means "look here first." It does not remove the need to inspect the demo, compare the context, and look for repeat patterns across other matches when the case is close.

### Benchmark Slice Comparison

![Benchmark slice comparison](assets/plots/benchmark_slice_signals.png)

### Cheater Retrieval Summary

![Cheater retrieval summary](assets/plots/cheater_retrieval_summary.png)

## Desktop Beta

NullCS is now centered around the desktop review app. The beta workflow is:

1. Open the NullCS desktop app.
2. Drop in one Counter-Strike `.dem` file.
3. Run local analysis.
4. Review the ranked Players tab.
5. Open a player report when someone needs deeper inspection.

The desktop app accepts `.dem` files only. It does not analyze videos, screenshots, scoreboard images, or live matches.

The important interpretation rule is simple: a player landing in **Review** means the model sees signals that deserve follow-up. It does not automatically mean the player is cheating. Edge cases should be checked against the actual demo, round context, POV, teammate and opponent behavior, and ideally other matches from the same player.

The beta installer will be distributed through [GitHub Releases](https://github.com/gjones01/NullCS.ai/releases).

## Technical Docs

- [Proof and benchmark story](proof.html)
- [Model and pipeline overview](model.html)
- [Project scope](scope.html)
- [Full research snapshot](research_snapshot.html)
- [Full benchmark methodology](benchmark_methodology.html)

## Limitations

This repo is intentionally public-safe and does not expose:

- raw demo files
- private uploads
- internal evidence exports
- sensitive operational logic
- product packaging for a public end-user release

The current public story is best read as research progress and project documentation, not a claim of a finished enforcement-ready system.

## Next Steps

The next direction is to keep improving the quality of the evidence rather than simply adding more model complexity. The areas I care about most are stronger calibration, better control datasets, clearer per-player explanations, and more stress testing against legitimate high-skill play.

I also want to keep tightening the local application around the model. That means safer desktop packaging, clearer report exports, better failure handling, and a workflow that makes it easy to inspect a demo without exposing private data or overclaiming what the score means.

Longer term, I would like NullCS to become a polished example of applied ML engineering: a project that connects raw game telemetry, behavioral modeling, local tooling, documentation, and security-conscious packaging into one coherent system. Ultimately, this is a passion project that has led me deeper than I could have ever imagined.

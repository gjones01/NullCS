# NullCS

NullCS is a Counter-Strike 2 demo research project for behavioral anomaly detection.

It is **not** an anti-cheat, **not** a ban system, and **not** an automated verdict engine. The system turns post-match demo telemetry into ranked review signals: which players and engagements deserve closer inspection, and which measurements caused the model to raise them.

The current public benchmark uses 894 parsed demos and 281,792 encounter windows. After player-demo filtering, the grouped evaluation set contains 860 demos, 6,886 player-demo rows, 992 positive rows, and 5,894 negative rows.

## What Problem This Studies

Scoreboard statistics are too coarse for the cases NullCS is meant to study. A high headshot rate or a short reaction time can be meaningful, but those numbers are also affected by skill, weapon choice, angle advantage, map position, visibility, and round context.

NullCS asks a narrower question:

> Can tick-level demo telemetry surface unusual behavior for review while staying comparatively quiet on legitimate high-skill play?

The output is a triage surface. A high score means "look here first." It does not mean "this account cheated."

## Pipeline

```text
CS2 .dem file
  -> tick-level parse tables
  -> encounter windows around engagements
  -> 35-channel temporal encounter representation
  -> temporal CNN encounter scoring
  -> ~450 player-demo features
  -> grouped XGBoost ranking model
  -> ranked players, evidence rows, and reasons for review
```

The model stack is intentionally split:

- A temporal CNN reads fixed-length encounter windows with synchronized channels such as aim error, mouse delta, command/view gaps, visibility transitions, movement state, shot timing, and damage timing.
- Player-demo aggregation converts encounter outputs and engineered telemetry into 449 features.
- A gradient-boosted player-level model ranks players inside each demo.

## Feature Families

NullCS computes signals around the process leading into an engagement, not just the result.

- **Aim process:** aim error, aim collapse, angular velocity, angular jerk, crosshair correction, pre-shot stability.
- **Visibility and timing:** first visible tick, visibility transitions, time to first shot, time to damage, prefire-like windows.
- **Input and control path:** mouse delta magnitude, command yaw/pitch deltas, view-command gaps, post-acquire quietness, input burst behavior.
- **Movement and difficulty:** attacker/victim speed, walking, airborne state, scoped/flashed state, distance, closing speed, relative speed.
- **Outcome context:** kills, damage, headshot rate, through-smoke events, weapon mix, victim spread, round distribution.

## Current Results

Grouped out-of-fold evaluation is done by `demo_id`, so rows from the same match do not appear in both train and validation folds.

| Metric | Current CS2CD player-level result |
| --- | ---: |
| Evaluated demos after player-count filter | 860 |
| Evaluated player-demo rows | 6,886 |
| Positive / negative rows | 992 / 5,894 |
| ROC-AUC | 0.956 |
| PR-AUC | 0.796 |
| Confirmed suspicious player ranked top-1 | 92.8% |
| Confirmed suspicious player ranked top-3 | 97.3% |

These are review-ranking metrics, not enforcement metrics. See [RESULTS.md](RESULTS.md) for the detailed readout, behavioral observations, and failure cases.

## What It Actually Finds

The strongest current signals are not generic "AI detections." They are measurable differences in encounter and player behavior:

- confirmed suspicious player rows have much higher temporal encounter-model scores than negative rows;
- suspicious rows show more frequent high-scoring encounter clusters rather than only one isolated event;
- rifle prefire-like rates, long-range fast reaction patterns, and headshot concentration separate some positives from the negative baseline;
- some non-cheater demos still produce high scores, especially when a player has a strong headshot-heavy match with fast reaction streaks.

The last point matters. NullCS is useful only if the evidence remains inspectable when the model is wrong or uncertain.

## Documentation

- [METHODOLOGY.md](METHODOLOGY.md) explains data construction, feature engineering, modeling, and leakage controls.
- [RESULTS.md](RESULTS.md) reports the current benchmark metrics and failure cases.
- [PIPELINE.md](PIPELINE.md) lists the practical commands and artifact paths.

## Repository Scope

This repository contains the public-safe research code, documentation, benchmark summaries, and website source for NullCS. It does not ship raw demos, private match artifacts, secrets, or enforcement tooling.

## Acknowledgements

NullCS depends on [`demoparser2`](https://github.com/LaihoE/demoparser), maintained by LaihoE and contributors. That parser makes it practical to turn CS2 `.dem` files into structured data for research.

## License

This public repository does not currently grant an open-source license. The documentation is public for review and transparency, but redistribution of modified builds or repackaged artifacts should not be treated as an official NullCS release.

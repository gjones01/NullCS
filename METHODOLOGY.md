# Methodology

NullCS looks at post-match telemetry. It never judges an account from one round or
one kill. It ranks players and moments worth a human look, and keeps enough
evidence to explain why a score moved.

## 1. Data

Two sources feed the current artifacts:

- parsed CS2 demos from the original player-level pipeline (demoparser/AWPy based);
- the CS2CD benchmark set, split into matches with and without a known cheater.

Verified sizes:

| Item | Value |
| --- | ---: |
| Demos in the window-model data | 894 |
| Engagement windows | 281,792 |
| Demos in player evaluation (after the 8-player filter) | 860 |
| Player rows | 6,886 (992 positive / 5,894 negative) |

Labels are used to measure the research pipeline. They are not proof that every
elevated moment is cheating.

## 2. Engagement windows

A window is a short slice of ticks around one player-versus-player interaction.
Windows describe *process*, not only outcome:

- what the attacker could see, and when the target first became visible;
- how the aim moved before and after that moment;
- whether a shot or damage landed before the aim settled;
- how distance and movement changed;
- how mouse and view input behaved after the target was acquired.

## 3. Window model

A small temporal CNN reads fixed-length windows: 35 channels over 32 ticks. The
channels cover aim error, mouse delta, view/command gaps, distance and speed,
angular velocity and jerk, visibility state and transitions, movement state
(walking, airborne, scoped) and shot/damage timing.

The CNN scores windows only. Its scores are summarised per player (mean, top-k
mean, high-score rate and similar) and become inputs to the ranking model.

## 4. Player features

Per player and per demo the pipeline computes 449 features, in plain groups:

- **Counts:** kills, rounds, victims, weapons.
- **Reaction time:** typical value, spread, and how often it is very short.
- **Precision and habit:** headshot rate, through-smoke rate, prefire-like rate,
  long-range fast reactions, weapon mix.
- **Aim process:** how quickly aim settles, how noisy it stays, how it collapses
  onto the target.
- **Movement and context:** distance, speed, visibility exposure.
- **Window-model summaries.**

Identifiers such as SteamID and player name are never used as features.

## 5. Ranking model

Gradient-boosted trees over the 449 features, evaluated with grouped
cross-validation:

- groups are demo IDs, so a match never lands in both training and validation;
- class imbalance is handled with data-dependent weighting;
- the saved scores are isotonic-calibrated, which improves Brier score and log loss.

Calibrated or not, the output is a review priority, not a probability suitable for
enforcement.

## 6. Keeping ourselves honest

- **Grouped splits** by demo ID prevent same-match leakage.
- **Identifiers are excluded** from the feature set.
- **The feature list is locked** to a published 449-feature file, so a training run
  cannot silently change the contract, and the manifest records which file was used.
- **Training and inference share one aggregation implementation**, so served
  features cannot drift from trained features.
- **Known limit:** the split is match-isolated but not chronological. It measures
  generalisation across demos, not future drift.

## 7. How to read a score

| Score | What to do |
| --- | --- |
| High | Inspect this player first. |
| Medium | Check whether the evidence is concentrated or thin. |
| Low | The measured behaviour did not stand out. |

No single feature and no single score is a verdict.
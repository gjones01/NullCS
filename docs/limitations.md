# Limitations And Research Boundaries

NullCS is a research project for behavioral review and analyst triage. Its outputs should be interpreted cautiously.

## Not An Enforcement System

NullCS is not:

- a live anti-cheat
- a ban system
- a verdict engine
- a detector for a specific cheat category
- a replacement for demo review

The system surfaces unusual behavior and review-worthy anomalies. It does not directly label someone as walling, aim assisting, or using any specific tool.

## Single-Match Uncertainty

One demo is a limited sample. Match-relative ranking can highlight a standout, but it cannot establish a long-term account-level conclusion. Edge cases should be compared against:

- the actual POV/demo
- round context
- teammate and opponent information
- utility and visibility context
- repeated behavior across other matches

## Label Limitations

Labels are imperfect. Suspicious benchmark labels can be incomplete, noisy, or tied to a player rather than every individual encounter. A labeled suspicious player does not make every kill suspicious. A clean label does not prove every moment is ordinary.

This is why grouped validation, review-oriented outputs, and conservative interpretation matter.

## High-Skill False Positives

Strong legitimate players can produce unusual aim, timing, and conversion patterns. High-ELO and pro-style play are important stress tests because false positives there are especially damaging. A research system that cannot stay quiet on strong legitimate slices is not credible.

## Subtle Behavior Is Hard

Obvious abuse is easier to surface. Subtle irregular behavior is harder because it can intentionally stay close to normal mechanical play. This makes uncertainty unavoidable and makes overclaiming especially risky.

## Match-Relative Scores Are Not Probabilities

A high match-relative signal is not a universal probability that a player cheated. It means the player should be reviewed sooner inside that match. Low signal does not prove innocence, and high signal does not settle the case.

## Current Status

The project has meaningful feature engineering, modeling, and evaluation work behind it, but it remains an active research effort. The current outputs should be read as research progress and analyst-triage support, not as finished enforcement technology.

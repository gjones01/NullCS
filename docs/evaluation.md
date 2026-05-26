# Evaluation Philosophy

NullCS is evaluated as an analyst-triage system, not as an automated enforcement classifier. This changes what good performance means.

## Why ROC-AUC And PR-AUC Are Not Enough

ROC-AUC and PR-AUC are useful for measuring discrimination under labeled evaluation. They are not sufficient for this project because the practical use case is review ordering inside a match.

A model can have good aggregate metrics while still being unhelpful if:

- it ranks the wrong player first in suspicious matches
- it inflates strong legitimate players
- it produces noisy scores across clean or pro-like demos
- it cannot provide interpretable reasons
- it performs well only on obvious cases

The evaluation has to reflect how a reviewer would use the output.

## Retrieval-Oriented Evaluation

Top-1 and top-3 retrieval ask whether a labeled suspicious player appears near the front of the review queue. Top-3 matters because triage is not a one-click decision. A reviewer can reasonably inspect the first few candidates in a lobby.

This is different from asking whether the model can make a final account-level claim. It only asks whether the model helps direct attention.

## Quiet Legit And Pro Slices

False positives on high-skill legitimate players are one of the most important failure modes. A model that treats every strong player as suspicious is not useful.

For that reason, normal legitimate and pro stress-test slices are evaluated for quietness. The system should surface suspicious benchmark cases more strongly while keeping legit and pro slices compressed near low signal.

## Match-Relative Framing

NullCS ranks players inside the current match. This is a deliberate limitation. Match-relative ranking avoids pretending that a single demo can produce a stable long-term account judgment.

The tradeoff is that match context matters. A weak lobby can make a strong legitimate player look unusual. A small number of encounters can make a signal unstable. Evaluation therefore has to consider support, sample size, and uncertainty.

## Review Output Quality

A useful output should include:

- ranking position
- signal strength
- support level
- reason summaries
- evidence tables
- limitations
- context that weakens or strengthens the read

The goal is not just to score. The goal is to make the score inspectable.

## Current Public Read

The public benchmark story is strongest when two things are true at once:

1. suspicious benchmark slices rise toward the top of review ordering
2. held-out legit and pro slices stay quiet

That combination is more important than a single headline metric.

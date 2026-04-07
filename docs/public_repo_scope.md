# Public Repo Scope

This repo is meant to present the public-safe research side of NullCS.

## Intended Public Content

The following categories are appropriate for the public repo:

- source code for public-safe research components
- feature engineering and modeling code that does not expose private data
- benchmark methodology and high-level benchmark summaries
- public-safe plots derived from aggregate findings
- written research notes and experiment conclusions

## Content Intentionally Kept Private

The following should remain out of the public repo:

- raw demo files
- uploaded match files
- processed local artifacts
- report exports and evidence tables
- model binaries and private training artifacts
- desktop app packaging and private operational integration code
- credentials, environment files, and local service state

## Desktop App Policy

The desktop application is not part of the intended public GitHub presentation.

For the public repo, the emphasis should remain on:

- the research project
- the benchmark story
- the modeling pipeline
- public-safe plots and findings

That keeps the GitHub presentation tighter and reduces accidental exposure of local-only operational codepaths.

## Documentation Standard

Public docs should:

- explain what the system is doing at a high level
- use research-first framing
- describe signals as review inputs, not verdicts
- avoid filesystem-specific private notes
- avoid local path leaks and operational secrets

Public docs should not:

- publish internal handoff notes
- publish local environment guides tied to private data
- publish desktop-integration debugging history
- publish sensitive implementation details that are unnecessary for understanding the research

## Repo Hygiene

Before pushing publicly, verify that the repo does not include:

- ignored data directories
- generated evidence exports
- local reports
- private plots unrelated to the public research narrative
- one-off marketing assets that are not part of the repo story

The public repo should read like a research codebase, not a local working dump.


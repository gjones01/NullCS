# Security Policy

## Scope

NullCS is a research and review tool. Public deployments must not include private datasets, demo uploads, model artifacts, or generated evidence files.

## What Is Stored

- Source code
- Public documentation
- Frontend assets required to render the UI

## What Must Not Be Committed Or Publicly Served

- `huggfacedata/` and `huggingfacedata/`
- `main/data/processed/**`
- `main/data/raw_uploads/**`
- Any `*.dem`, `*.parquet`, model artifact, report export, log, or `.env` file
- Private API keys or credentials

## Deployment Expectation

- Public frontend deployments should run in demo mode only.
- Full inference should remain local or on a private backend with restricted access.
- Production analysis endpoints require `X-NULLCS-KEY` from `NULLCS_API_KEY`.

## Responsible Disclosure

Report security issues privately. Include:

- Affected file or endpoint
- Reproduction steps
- Impact assessment
- Suggested mitigation if available

Do not publish working exploits, private data, or secrets in public issues.

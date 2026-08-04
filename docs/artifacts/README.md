# Documentation artifacts

This directory is the single home for generated or captured project evidence.
The maintained source documentation remains in `docs/`; exports, screenshots,
reports and snapshots belong here.

## Structure

| Directory | Store here |
| --- | --- |
| [`ui/`](ui/) | Sanitized mobile/desktop screenshots, mockups and interaction recordings |
| [`architecture/`](architecture/) | Rendered diagrams, schema exports and API snapshots |
| [`qa/`](qa/) | Test summaries, responsive checks and release-verification reports |

## Naming

Use lowercase kebab-case and include the milestone or date when useful:

- `v1-mobile-home-dark.png`
- `v1-database-erd.svg`
- `2026-08-04-release-verification.md`

## Safety rules

- Use fictional names, accounts, merchants and balances only.
- Never commit credentials, tokens, production exports or real financial data.
- Prefer text or SVG for diagrams so changes remain reviewable.
- Keep source-of-truth decisions and requirements in the parent `docs/` folder.
- Link every material artifact from this index or its directory index.

## Current artifacts

- [V1 QA scenario matrix](qa/v1-scenario-matrix.md)
- [V1 public-release verification](qa/v1-public-release.md)
- [Production staging verification](qa/production-staging-verification.md)
- [Personal Supabase launch verification](qa/2026-08-04-personal-supabase.md)
- [UI artifact guide](ui/README.md)
- [Architecture artifact guide](architecture/README.md)

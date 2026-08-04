# Contributing to Artha

Thank you for helping make personal money tracking simpler and more trustworthy.

## Before starting

For a substantial feature or data-model change, open a feature request first.
Bug fixes and documentation improvements can go directly to a pull request.

Never submit real transaction data, account identifiers, access tokens,
database URLs or screenshots containing personal balances.

## Development setup

```bash
git clone https://github.com/snayan06/artha.git
cd artha
cp .env.example .env
make setup
make dev-api
```

Run `make dev-web` in a second terminal.

## Product invariants

- Store money as integer paise, never floating point.
- Parsing creates an unsaved draft; it cannot write to the ledger.
- Financial writes require explicit confirmation and an idempotency key.
- Account movement and personal expense share remain separate.
- Transfers and settlements are not income or spending.
- Production data must remain isolated through verified authentication and RLS.
- Agent tools are read-only and return validated, source-linked data.

## Pull requests

1. Keep changes focused and explain the user-visible outcome.
2. Add or update tests for ledger, parser and API-contract changes.
3. Run `make check` locally.
4. Update the relevant documentation and task checklist.
5. Use fictional values in tests and screenshots.

CI must pass before merge. By participating, you agree to follow the
[Code of Conduct](CODE_OF_CONDUCT.md).

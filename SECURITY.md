# Security policy

Artha handles private financial records. Do not open public issues containing transaction data, access tokens, account labels, database URLs or screenshots of real balances.

## Design controls

- Supabase Row Level Security is mandatory on every exposed production table.
- Normal user requests never use a service-role credential.
- Transaction parsing returns an unsaved draft.
- Financial writes require explicit confirmation and an idempotency key.
- The V2 agent has read-only tools and cannot execute SQL or arbitrary UI code.
- Secrets stay in server-side environment variables and deployment secret stores.

## Reporting a problem

Do not open a public issue for a suspected vulnerability. Use GitHub's
[private vulnerability reporting](https://github.com/snayan06/artha/security/advisories/new)
or contact the repository owner privately. Include reproduction steps using
fictional data only.

The current V1 is a local/private-pilot build. Production mode is intentionally
disabled until signed JWT verification, the Supabase repository adapter and
live cross-household RLS tests are complete.

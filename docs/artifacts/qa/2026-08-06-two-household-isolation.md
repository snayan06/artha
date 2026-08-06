# Two-household isolation acceptance layer

Date: 6 August 2026
Status: implemented and statically validated; behavioral execution pending

## Purpose

Artha needs two independent proofs before real financial data is allowed:

1. local database behavior under authenticated and anonymous RLS roles; and
2. read-only verification against the hosted Supabase project using two real,
   already-onboarded test identities.

The two checks added here never store credentials or production financial data.

## Local transactional behavior test

[`supabase/tests/003_two_household_isolation.sql`](../../../supabase/tests/003_two_household_isolation.sql)
creates two fixed fictional auth users, profiles, households, owner memberships
and accounts inside one transaction. It then impersonates each authenticated
JWT subject and verifies:

- each user sees only its own profile, household, members and accounts;
- each user resolves only its own current household;
- a user can insert an account in its own household;
- a cross-household account insert is rejected by RLS;
- a cross-household update affects zero rows;
- `get_account_balances` rejects the other household; and
- the anonymous role cannot read accounts.

The file ends with `rollback`, so fixtures do not survive a successful or failed
test transaction.

Run it after the local Supabase stack is healthy:

```bash
supabase test db
```

## Hosted token-only checker

[`scripts/check_two_household_tokens.py`](../../../scripts/check_two_household_tokens.py)
is deliberately read-only. It requires these values from the process environment:

- `ARTHA_SUPABASE_URL`
- `ARTHA_SUPABASE_ANON_KEY`
- `ARTHA_USER_A_TOKEN`
- `ARTHA_USER_B_TOKEN`

The project URL must be a bare HTTPS origin. Tokens are decoded only to compare
their UUID subjects, then sent to the configured Supabase project. The script
never prints tokens, authorization headers, emails, row contents or household
identifiers. Do not place tokens in command-line arguments, source control,
shell history, screenshots, chat or `.env` files.

After setting the four variables through a protected ephemeral environment, run:

```bash
python scripts/check_two_household_tokens.py
```

The two identities must already be onboarded into different households. The
checker verifies:

- each token sees exactly its own profile and one own household;
- every visible row across members, accounts, categories, transactions, splits,
  settlements, transfers, merchant rules and audit events belongs to that
  token's household;
- explicit filters for the other household return zero rows on every table;
- each token's cross-household balance RPC is denied; and
- anonymous account access is denied or returns zero rows.

Expected sanitized success output:

```text
hosted-two-household-ok users=2 households=2 scoped_rows=<count> cross_rows=0 cross_rpc_denials=2 anon_rows=0
```

This hosted checker intentionally performs no inserts, updates or deletes. The
transactional local SQL test covers write-policy behavior; the older
service-key fixture runner remains available for a controlled disposable
environment when full create/cleanup coverage is required.

## Validation completed

| Check | Result |
| --- | --- |
| Ruff on hosted checker | Pass |
| Python bytecode compilation | Pass |
| PostgreSQL parse of all migrations, seed and three SQL tests | Pass |
| `003_two_household_isolation.sql` behavioral execution | Blocked: local Docker daemon/Supabase stack is not running |
| Hosted two-token execution | Blocked: two user-controlled onboarded tokens were not available and must not be pasted into chat |

## Remaining acceptance actions

1. Start Docker and the local Supabase stack, then run `supabase test db`.
2. Sign in and onboard two fictional test identities into different households.
3. Expose both short-lived access tokens only to a protected local process and
   run the hosted checker.
4. Store only the sanitized success line and timestamp in this artifact; never
   store credentials or row payloads.

Until both behavioral runs pass, the fresh personal production database remains
**not approved for real financial data**.

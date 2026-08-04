# Personal Supabase launch verification

Date: 4 August 2026

## Environment

- Owner: personal Supabase organization for `snayan06`
- Project: `artha-production`
- Project reference: `vggvufukkkirlwxqkjhz`
- Region: South Asia (Mumbai), `ap-south-1`
- Project URL: `https://vggvufukkkirlwxqkjhz.supabase.co`
- Data API: enabled
- Automatic exposure of new tables: disabled
- Automatic RLS for new tables: enabled
- Database password: stored outside the repository in macOS Keychain; value not recorded here
- Supabase GitHub integration: intentionally not connected for V1 because migrations already have one reviewed deployment path from this repository

## Applied migrations

1. `20260804010000_initial_ledger.sql`
2. `20260804020000_ledger_p1_hardening.sql`
3. `20260804030000_credit_card_setup.sql`
4. `20260804040000_production_safety_contracts.sql`
5. `20260804050000_authenticated_data_api_grants.sql`

## Verification results

- Remote migration dry-run: up to date; no pending migrations
- Remote `public` schema lint: no schema errors
- Hosted catalog assertions: passed
- Required tables: RLS enabled
- Ledger money columns: integer `bigint` paise
- Production safety RPCs and grants: present and hardened
- Anonymous ledger table grants: absent
- Auth JWKS: one asymmetric `ES256` key, supported by the API verifier
- Direct database endpoint: IPv6-only from this machine
- Migration connection: Supabase IPv4 session pooler in Mumbai; credentials not recorded

## Still required before real financial data

- Run anonymous-denial behaviour against the public API.
- Onboard two real test identities into separate households and prove cross-household isolation.
- Complete final-domain login, refresh, sign-out and ledger acceptance.
- Complete encrypted export and restore testing.

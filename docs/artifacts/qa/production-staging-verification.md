# Production staging verification

Date: 4 August 2026  
Supabase project: legacy staging only; the tested project is under the wrong
account and must not receive real Artha data.

## Applied database contracts

- Five versioned migrations applied successfully.
- Eleven public tables have Row Level Security enabled.
- Authenticated Data API access is explicitly granted; anonymous table access is revoked.
- Household setup, current-household selection and audited transaction voiding are RPC-only.
- The final active household owner cannot be removed or demoted accidentally.

## Live isolation exercise

The repeatable [`scripts/check_live_rls.py`](../../../scripts/check_live_rls.py)
check creates two fictional confirmed users and separate households, exercises the
production FastAPI JWT and Supabase REST/RPC repository, and verifies:

- each user sees exactly one own household;
- neither user can read the other household;
- anonymous account reads return no data;
- onboarding and dashboard balances work through the production API;
- all fictional users and household rows are removed afterward.

Latest result:

```text
live-production-ok api_jwt=1 api_repository=1 users=2 households=2 cross_household_rows=0 anon_rows=0
fictional-test-data-cleaned
```

## Remaining final-domain gate

- Deploy the FastAPI and PWA final URLs.
- Configure exact CORS and Supabase magic-link redirect URLs.
- Verify email login, session reload and sign-out on the final domain.
- Complete encrypted export and restoration testing before entering real finance data.

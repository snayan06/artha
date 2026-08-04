# Sprint 1 deployment verification

Date: 5 August 2026  
Commit: `623f2ca`  
Result: public build and anonymous security smoke passed; authenticated acceptance pending

## Passed

- GitHub main contains the Sprint 1 commit.
- GitHub API, Web and Supabase SQL jobs completed successfully.
- GitHub CodeQL JavaScript/TypeScript and Python analyses completed successfully.
- Vercel completed both `artha-web` and `artha-api` production deployments from the same commit.
- Public web root returned HTTP 200 and loaded the new login copy after the PWA update activated.
- API `/health` returned HTTP 200 with `v1-production`.
- Vercel routing changed from Mumbai → Washington to Mumbai → Mumbai (`bom1::bom1`).
- Anonymous requests to accounts, profile and transactions each returned HTTP 401.
- CORS preflight allowed the exact production web origin with credentials.

## Still blocked

- Magic-link callback, refresh, tab/browser reopen and sign-out on the final domain.
- Authenticated onboarding/profile hydration on a second browser/device.
- Authenticated backdated expense, family split and atomic transfer smoke.
- Independent-owner hosted RLS isolation.
- 320 px and 390 px final-domain manual visual pass.
- Encrypted export/restore recovery gate.

Use fictional data until these blockers are cleared.


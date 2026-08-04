# Personal Vercel launch verification

Date: 4 August 2026

## Environment

- Owner: personal Vercel Hobby account for `snayan06`
- Source: public `snayan06/artha` GitHub repository, `main` branch
- PWA project: `artha-web`
- PWA URL: `https://artha-web-one.vercel.app`
- API project: `artha-api`
- API URL: `https://artha-api-mu.vercel.app`
- Supabase project: `artha-production`
- Supabase URL: `https://vggvufukkkirlwxqkjhz.supabase.co`
- Vercel account 2FA: enabled during launch setup
- Hosted model: disabled until ledger acceptance passes

No passwords, tokens, JWTs or private keys are recorded in this artifact.

## Deployment verification

- API root: `apps/api`
- API framework: FastAPI
- API entrypoint: `apps/api/src/app.py`
- API production health: HTTP 200 with `v1-production`
- Web root: `apps/web`
- Web framework: Vite
- Web production root: HTTP 200
- SPA direct routes `/transactions`, `/shared`, `/add` and `/assistant`: HTTP 200
- Web build uses the production API URL and Supabase publishable key.
- API exact CORS origin: `https://artha-web-one.vercel.app`
- Supabase Auth site URL: `https://artha-web-one.vercel.app`
- Supabase Auth redirect allow-list: the same exact PWA origin

## Build issue resolved

The first API deployment could not resolve `artha_api.app:app` through the
repository's `src` package layout. A recognized `src/app.py` entrypoint shim was
added and passed Ruff, strict mypy, all 79 API tests and a production import
check before the successful deployment.

## Still required before real financial data

- Verify magic-link login, refresh persistence and sign-out on the production PWA.
- Exercise two independent test identities and prove cross-household isolation.
- Complete the four-account, multi-card, backdated and family-split scenarios.
- Complete 320 px, 390 px and desktop visual QA in both themes.
- Complete encrypted export and restore testing.

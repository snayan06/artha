# Artha deployment runbook

The repository is designed to run locally without cloud credentials. Production deployment has three separately controlled surfaces.

## 1. Supabase

Five migrations and the live two-household RLS exercise passed against a legacy
staging project. That project is under the wrong account and is not approved for
real Artha data. Create a fresh project under the user's personal account and
repeat the complete exercise before launch.

1. Create a new Supabase project in the Mumbai region when available.
2. Link the local project with the Supabase CLI.
3. Review migrations under `supabase/migrations` before applying them.
4. Apply migrations and verify RLS is enabled on every exposed table.
5. Configure magic-link redirect URLs for the Pages preview and production domains.
6. Copy only the project URL and publishable/anon key to the web deployment.

Never expose the service-role key in the browser. Normal FastAPI requests should preserve the signed-in user's authorization context so RLS remains effective.

## 2. FastAPI private pilot on Render Free

Create a Python Web Service rooted at `apps/api`.

- Build command: `pip install uv && uv sync --frozen --no-dev`
- Start command: `uv run uvicorn artha_api.app:app --host 0.0.0.0 --port $PORT`
- Health check: `/health`
- Python: `3.13`

Set server-side environment variables from `.env.example`. Never enable automatic paid upgrades. Render Free sleeps after idle time, so its first request may be slow.

The checked-in `render.yaml` uses `ARTHA_ENV=production`. Production mode never
creates or connects to the SQLite demo database: it verifies Supabase JWTs and
forwards the same user bearer through the separate REST/RPC repository so RLS
remains active. Configure `SUPABASE_URL` and `SUPABASE_ANON_KEY` only; never add
the service-role key to the Render application.

For a production upgrade, use a paid Render instance or Google Cloud Run with a billing budget and hard alerts. Do not switch simply to hide cold starts without adding cost controls.

## 3. React PWA on Cloudflare Pages

Create a Pages project from the public GitHub repository.

- Root directory: `apps/web`
- Build command: `npm ci && npm run build`
- Output directory: `dist`
- `VITE_API_URL`: deployed FastAPI origin
- `VITE_DEMO_MODE`: `false`
- `VITE_SUPABASE_URL`: Supabase project URL
- `VITE_SUPABASE_ANON_KEY`: Supabase publishable/anon key

Static deployments contain no secrets. Supabase's publishable key is acceptable in the client only when RLS policies are correct.
Add the final Pages origin to Supabase Auth's site URL and allowed redirect URLs.
The browser persists the Supabase session, refreshes short-lived access tokens,
and sends the current bearer token to FastAPI; never place a service-role key in
any `VITE_` variable.

## Acceptance before calling production green

Current status: **legacy staging data path green, personal deployment pending**. Production
JWT verification, repository access, anonymous denial and two-household live RLS
isolation pass. Do not enter real finance data until the remaining final-domain
and recovery gates below pass.

- Magic-link login works on the final Pages domain.
- [x] A user cannot read another household through the API or direct Supabase calls.
- Quick Add creates a draft and does not write before confirmation.
- A confirmed shared transaction updates account movement, personal spend and every selected member's receivable correctly.
- Reload preserves the authenticated session and confirmed transaction.
- CSV export reconstructs the ledger.
- [x] Mobile widths 320 px and 390 px have no overflow.
- API and browser logs contain no tokens or financial payloads.
- A manual encrypted export is downloaded and restoration is tested.

# Hisab deployment runbook

The repository is designed to run locally without cloud credentials. Production deployment has three separately controlled surfaces.

## 1. Supabase

1. Create a new Supabase project in the Mumbai region when available.
2. Link the local project with the Supabase CLI.
3. Review migrations under `supabase/migrations` before applying them.
4. Apply migrations and verify RLS is enabled on every exposed table.
5. Configure magic-link redirect URLs for the Pages preview and production domains.
6. Copy only the project URL and publishable/anon key to the web deployment.

Never expose the service-role key in the browser. Normal FastAPI requests should preserve the signed-in user's authorization context so RLS remains effective.

## 2. FastAPI disposable preview on Render Free

Create a Python Web Service rooted at `apps/api`.

- Build command: `pip install uv && uv sync --frozen --no-dev`
- Start command: `uv run uvicorn hisab_api.app:app --host 0.0.0.0 --port $PORT`
- Health check: `/health`
- Python: `3.13`

Set server-side environment variables from `.env.example`. Never enable automatic paid upgrades. Render Free sleeps after idle time, so its first request may be slow.

The checked-in `render.yaml` uses `HISAB_ENV=preview` and ephemeral SQLite. It is
only for UI/API evaluation: data can disappear after a restart or redeploy. Do
not enter real financial data. `HISAB_ENV=production` intentionally refuses to
start until the Supabase repository and verified JWT authentication are wired.

For a production upgrade, use a paid Render instance or Google Cloud Run with a billing budget and hard alerts. Do not switch simply to hide cold starts without adding cost controls.

## 3. React PWA on Cloudflare Pages

Create a Pages project from the public GitHub repository.

- Root directory: `apps/web`
- Build command: `npm ci && npm run build`
- Output directory: `dist`
- `VITE_API_URL`: deployed FastAPI origin
- `VITE_DEMO_MODE`: `false`

Static deployments contain no secrets. Supabase's publishable key is acceptable in the client only when RLS policies are correct.

## Acceptance before calling production green

Current status: **not production green**. Local V1 behavior is verified; the
remaining authentication, production repository and live-RLS gates below are
deliberately blocking a real-data deployment.

- Magic-link login works on the final Pages domain.
- A user cannot read another household through the API or direct Supabase calls.
- Quick Add creates a draft and does not write before confirmation.
- A confirmed shared transaction updates account movement, personal spend and every selected member's receivable correctly.
- Reload preserves the authenticated session and confirmed transaction.
- CSV export reconstructs the ledger.
- Mobile widths 320 px and 390 px have no overflow.
- API and browser logs contain no tokens or financial payloads.
- A manual encrypted export is downloaded and restoration is tested.

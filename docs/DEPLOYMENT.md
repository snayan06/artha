# Artha deployment runbook

The private-pilot topology is two Vercel Hobby projects plus one Supabase Free
project. All three must be owned by the user's personal account; the legacy
`aarshiimagingcenter` Supabase/hosting accounts are explicitly out of scope.

## Environment inventory

| Surface | Target owner | Project | Expected URL |
|---|---|---|---|
| Source and CI | GitHub `snayan06` | `artha` | `github.com/snayan06/artha` |
| PWA | Personal Vercel account | `artha-web` | `https://artha-web-one.vercel.app` |
| API | Personal Vercel account | `artha-api` | `https://artha-api-mu.vercel.app` |
| Auth and data | Personal Supabase organization | `artha-production` | `https://vggvufukkkirlwxqkjhz.supabase.co` |

Record the actual project IDs and URLs in `docs/artifacts/qa/` after creation.
Do not record passwords, access tokens, JWTs or private keys.

## 1. Fresh Supabase project

The five versioned migrations and live two-household RLS exercise passed against
a legacy staging project. That project is under the wrong account and must never
hold real Artha data.

1. Sign into Supabase with the user's personal account, not
   `aarshiimagingcenter`.
2. Create `artha-production` on the Free plan in Mumbai when available.
3. Link the repository with the Supabase CLI without saving a database password
   in source.
4. Apply every migration under `supabase/migrations` to the empty project.
5. Refresh and verify the PostgREST function catalog; migration history alone
   does not prove that a new RPC is callable through Supabase REST.
6. Run the SQL catalog checks and the live anonymous/two-household RLS exercise.
7. Confirm Auth uses an asymmetric signing key supported by the API JWKS verifier.
8. Initially set the Auth site URL and redirect allow-list to the final PWA
   `vercel.app` origin only.

Only the project URL and publishable/anon key go to Vercel. Never expose the
service-role key. FastAPI forwards each user's bearer token to Supabase so RLS
remains the authorization boundary.

## 2. FastAPI on Vercel Hobby

Import `https://github.com/snayan06/artha` into a personal Vercel account as a
project named `artha-api`.

- Root directory: `apps/api`
- Framework: FastAPI/Python auto-detection
- Entrypoint: recognized `src/app.py` shim exporting `artha_api.app:app`
- Build/output overrides: none
- Health check after deployment: `GET /health`

Production environment variables:

```dotenv
ARTHA_ENV=production
ARTHA_CORS_ORIGINS=https://artha-web-one.vercel.app
SUPABASE_URL=https://vggvufukkkirlwxqkjhz.supabase.co
SUPABASE_ANON_KEY=<publishable-or-anon-key>
SUPABASE_JWT_AUDIENCE=authenticated
ARTHA_LLM_PROVIDER=disabled
```

Use the actual PWA origin if Vercel assigns a different name. Do not add the
service-role key. Keep the hosted model disabled until the ledger acceptance gate
passes; later, add the Groq key only to `artha-api`.

## 3. React PWA on Vercel Hobby

Import the same repository as a second project named `artha-web`.

- Root directory: `apps/web`
- Framework preset: Vite
- Install command: `npm ci`
- Build command: `npm run build`
- Output directory: `dist`

Production environment variables:

```dotenv
VITE_API_URL=https://artha-api-mu.vercel.app
VITE_DEMO_MODE=false
VITE_SUPABASE_URL=https://vggvufukkkirlwxqkjhz.supabase.co
VITE_SUPABASE_ANON_KEY=<publishable-or-anon-key>
```

Every `VITE_` value is compiled into the public client bundle; only the Supabase
publishable key is allowed. `vercel.json` provides SPA route fallback for direct
loads of `/transactions`, `/shared`, `/add` and `/assistant`.

After both deployments exist, update the API's exact CORS origin and Supabase's
site/redirect URLs, then redeploy both projects. Do not use wildcard CORS.

## 4. Free-tier constraints

- Vercel Hobby is for personal non-commercial use and has included usage caps.
- Vercel's Python runtime is beta and the FastAPI application must remain within
  function duration and 500 MB bundle limits.
- Supabase Free can pause after low activity and provides no managed backups.
- A custom domain and WhatsApp Business messaging are outside the ₹0 promise.
- `render.yaml` is retained only as a fallback; Render Free's idle wake-up can
  take about a minute.

The application now fails closed instead of showing fictional demo balances when
the production API is unavailable.

After every migration that creates or replaces an RPC, run:

```bash
export ARTHA_SUPABASE_PROJECT_REF=<exact-ref-from-the-deployed-web-project-url>
supabase link --project-ref "$ARTHA_SUPABASE_PROJECT_REF"
make check-supabase-link
supabase db push --linked
make check-supabase-link
supabase db query --linked "notify pgrst, 'reload schema';"
ARTHA_SUPABASE_URL=<project-url> \
ARTHA_SUPABASE_ANON_KEY=<publishable-key> \
ARTHA_SUPABASE_PROJECT_REF="$ARTHA_SUPABASE_PROJECT_REF" \
make check-live-rpc-catalog
```

Resolve the expected project ref from the Supabase URL configured in the
deployed web project, not from a remembered CLI link or project display name.
`make check-supabase-link` is a mandatory fail-closed guard immediately before
every `--linked` write. If the CLI account cannot link to that exact project,
stop and use an authorized project owner instead of switching to another
project.

The live catalog probe sends no user token or ledger payload. A `PGRST202`/404
is a failed release even when `supabase migration list --linked` is synchronized.

## Acceptance before calling production green

Current status: **personal infrastructure live; authenticated final-domain and recovery acceptance pending**.
Do not enter real financial data until every unchecked item passes.

- [ ] Magic-link login works on the final PWA domain.
- [x] Required RPCs resolve through live PostgREST after the production migration.
- [ ] Reload, token refresh and sign-out work without losing a confirmed entry.
- [ ] Two test identities can onboard separate households and cannot read each
  other's API or direct Supabase data.
- [ ] Quick Add creates only a draft before confirmation.
- [ ] A confirmed shared transaction updates account movement, personal spend and
  every selected member receivable correctly.
- [ ] Four bank accounts, multiple cards and a backdated entry work end to end.
- [x] Direct loads of every PWA route return the application rather than 404.
- [ ] Mobile widths 320 px and 390 px plus desktop pass in light and dark modes.
- [ ] API and browser logs contain no tokens or financial payloads.
- [ ] Encrypted export reconstructs the ledger and a restore drill succeeds.
- [x] Final URLs, owners, project IDs and sanitized evidence are stored under
  `docs/artifacts/qa/`.

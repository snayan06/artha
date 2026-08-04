# Artha deployment runbook

The private-pilot topology is two Vercel Hobby projects plus one Supabase Free
project. All three must be owned by the user's personal account; the legacy
`aarshiimagingcenter` Supabase/hosting accounts are explicitly out of scope.

## Environment inventory

| Surface | Target owner | Project | Expected URL |
|---|---|---|---|
| Source and CI | GitHub `snayan06` | `artha` | `github.com/snayan06/artha` |
| PWA | Personal Vercel account | `artha-web` | `https://artha-web.vercel.app` or assigned equivalent |
| API | Personal Vercel account | `artha-api` | `https://artha-api.vercel.app` or assigned equivalent |
| Auth and data | Personal Supabase organization | `artha-production` | `https://<new-project-ref>.supabase.co` |

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
5. Run the SQL catalog checks and the live anonymous/two-household RLS exercise.
6. Confirm Auth uses an asymmetric signing key supported by the API JWKS verifier.
7. Initially set the Auth site URL and redirect allow-list to the final PWA
   `vercel.app` origin only.

Only the project URL and publishable/anon key go to Vercel. Never expose the
service-role key. FastAPI forwards each user's bearer token to Supabase so RLS
remains the authorization boundary.

## 2. FastAPI on Vercel Hobby

Import `https://github.com/snayan06/artha` into a personal Vercel account as a
project named `artha-api`.

- Root directory: `apps/api`
- Framework: FastAPI/Python auto-detection
- Entrypoint: `artha_api.app:app` from `pyproject.toml`
- Build/output overrides: none
- Health check after deployment: `GET /health`

Production environment variables:

```dotenv
ARTHA_ENV=production
ARTHA_CORS_ORIGINS=https://artha-web.vercel.app
SUPABASE_URL=https://<new-project-ref>.supabase.co
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
VITE_API_URL=https://artha-api.vercel.app
VITE_DEMO_MODE=false
VITE_SUPABASE_URL=https://<new-project-ref>.supabase.co
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

## Acceptance before calling production green

Current status: **legacy staging data path green; personal deployment pending**.
Do not enter real financial data until every unchecked item passes.

- [ ] Magic-link login works on the final PWA domain.
- [ ] Reload, token refresh and sign-out work without losing a confirmed entry.
- [ ] Two test identities can onboard separate households and cannot read each
  other's API or direct Supabase data.
- [ ] Quick Add creates only a draft before confirmation.
- [ ] A confirmed shared transaction updates account movement, personal spend and
  every selected member receivable correctly.
- [ ] Four bank accounts, multiple cards and a backdated entry work end to end.
- [ ] Direct loads of every PWA route return the application rather than 404.
- [ ] Mobile widths 320 px and 390 px plus desktop pass in light and dark modes.
- [ ] API and browser logs contain no tokens or financial payloads.
- [ ] Encrypted export reconstructs the ledger and a restore drill succeeds.
- [ ] Final URLs, owners, project IDs and sanitized evidence are stored under
  `docs/artifacts/qa/`.

# V1 security headers and offline state

Date: 5 August 2026
Status: implemented and verified locally; deployed-header check pending

## Security response policy

The API now adds `X-Content-Type-Options`, `X-Frame-Options`,
`Referrer-Policy` and a restrictive camera/microphone/geolocation
`Permissions-Policy` to every HTTP response. Production responses also receive
HSTS. `/api/` responses are marked `Cache-Control: no-store` so authenticated
financial payloads are not cached by shared browser or intermediary caches.

The web deployment defines the equivalent browser-facing hardening headers in
its Vercel configuration. A content security policy is intentionally not
invented in this change: the allowed Supabase and API origins are environment
specific and need a tested deployment-aware policy rather than a broad or
silently broken one.

## Network-state behavior

When the browser reports that it is offline, the authenticated shell shows an
accessible status banner. The copy says that already loaded information can be
reviewed but new changes cannot be saved until reconnection. V1 does not claim
to queue writes or save drafts offline.

## Code and tests

- API middleware: `apps/api/src/artha_api/security.py`
- API regression tests: `apps/api/tests/test_security_headers.py`
- Web deployment headers: `apps/web/vercel.json`
- Browser status hook: `apps/web/src/lib/network.ts`
- Offline UI and tests: `apps/web/src/components/Shell.tsx` and
  `apps/web/src/components/Shell.test.tsx`

Focused API and web tests, strict Python typing, Ruff, TypeScript and ESLint all
pass locally. Production header checks are required after deployment.

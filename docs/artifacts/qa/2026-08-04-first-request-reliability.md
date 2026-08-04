# First-request reliability diagnosis

Date: 4 August 2026  
Status: local fix implemented; production deployment measurement pending

## Symptom

The first action sometimes showed a signal/API error and succeeded on retry.
Six direct health requests returned HTTP 200 in approximately 0.24-0.37 seconds,
so the API was not continuously unavailable. Response routing showed Mumbai
ingress with function execution in Washington while the database is in Mumbai.

## Changes

- Pin the FastAPI function to Vercel Mumbai (`bom1`) beside Supabase.
- Enable Vercel Fluid compute.
- Increase the browser timeout from 3.5 to 10 seconds.
- Retry reads, parse/chat requests and writes carrying an idempotency key once.
- Never retry unsafe onboarding writes automatically.
- Return a human-readable timeout or connection message.

## Safety

Retries are based on operation semantics, not convenience. A transaction confirm
may retry because the same idempotency key makes it replay-safe. Onboarding does
not retry because it is not yet explicitly replay-safe.

## Evidence and remaining check

Automated tests cover a failed-first GET, an idempotent confirmation retry and a
non-retried onboarding POST. Production must still be deployed and measured for
both cold and warm authenticated requests.

- Vercel placement: `apps/api/vercel.json`
- Browser retry policy: `apps/web/src/lib/api.ts`
- Retry tests: `apps/web/src/lib/api.test.ts`


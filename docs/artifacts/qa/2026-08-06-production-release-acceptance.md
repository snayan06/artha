# Production release acceptance checkpoint

Date: 6 August 2026  
Public web: `https://artha-web-one.vercel.app`  
Public API: `https://artha-api-mu.vercel.app`  
Release status: **not green for real financial data**

This checkpoint separates checks completed without user credentials from checks
that require real user-controlled sign-in links or a second test identity. Only
fictional inputs were used. No email address, token, authorization code, ledger
payload or production write is stored in this artifact.

## Source and automated gate

| Check | Result | Evidence |
| --- | --- | --- |
| Local complete gate | Pass | `make check` completed on local commit `b4d7ae3`: web ESLint and TypeScript passed; 80 web tests passed; Ruff and strict mypy passed; 96 API tests passed; production PWA build passed; SQL files parsed; 50 capture-evaluation cases validated |
| Public source revision | Pass | GitHub `main` was `82045a8` (`Harden Sprint 1 reliability and model evaluation`) during this checkpoint |
| GitHub CI for public revision | Pass | CI run `31104011034` and CodeQL run `31104010455` both completed successfully for `82045a8` |

The local checkout and public revision were not the same commit during this run,
so the local `make check` result is not presented as a direct execution of the
deployed commit. GitHub CI and CodeQL are the automated evidence for the public
revision.

## Executed public and local acceptance matrix

| ID | Surface | Scenario executed | Result | Observed evidence |
| --- | --- | --- | --- | --- |
| PUB-01 | Public web | Direct HTTP loads of `/`, `/transactions`, `/shared`, `/add` and `/assistant` | Pass | Every route returned HTTP 200 with `text/html`; browser direct loads of protected routes rendered the Artha sign-in gate rather than a 404 |
| PUB-02 | Public web | Current entry assets and client copy | Pass | Current JavaScript asset returned `application/javascript`; the deployed UI contained `Sign in to Artha`, the returning/new-user explanation and auth-recovery copy |
| PUB-03 | Public web | Security headers | Pass | Root returned HSTS, `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, strict referrer policy and a camera/microphone/geolocation-denying permissions policy |
| API-01 | Public API | Anonymous `GET /health` | Pass | HTTP 200, `{"status":"ok","version":"v1-production"}` and Vercel execution `bom1::bom1` |
| API-02 | Public API | Anonymous access to profile, accounts and transactions | Pass | All three protected endpoints returned HTTP 401; no demo or ledger data was returned |
| API-03 | Public API | Production-web CORS preflight | Pass | HTTP 200, exact `Access-Control-Allow-Origin: https://artha-web-one.vercel.app`, credentials enabled, `Vary: Origin`, and `Cache-Control: no-store` |
| AUTH-01 | Public web | Synthetic expired-link callback containing no real credential | Pass | Accessible alert said the link expired, offered a fresh-link action, and removed callback error parameters from the visible URL |
| AUTH-02 | Public web | Synthetic wrong-browser/missing-PKCE-verifier callback | Pass | Accessible alert explained that the secure verifier belongs to the requesting browser, offered a fresh-link action, and removed synthetic callback parameters |
| RSP-01 | Public sign-in | Exact 320 CSS px, light | Pass | No horizontal overflow; card, email field and 44 px primary action remained within the viewport |
| RSP-02 | Public sign-in | Exact 320 CSS px, dark | Pass | No horizontal overflow; background, text and input used the dark palette; visual inspection found no light-only panel |
| RSP-03 | Public sign-in | Exact 390 CSS px, light and dark | Pass | No horizontal overflow in either theme; controls remained within the viewport and at least 44 px high |
| RSP-04 | Public sign-in | Desktop 1344 × 895, light and dark | Pass | Content remained bounded and centered; no horizontal overflow; dark input and surface colors were applied |
| THEME-01 | Public sign-in | Theme control plus reload | Pass | System changed to explicit light, light persisted across reload, and light changed to dark with the expected DOM theme markers |
| OFF-01 | Public sign-in | Reload after browser network was set offline, then restore network | Pass | Installed PWA shell rendered the full sign-in screen offline; the app returned online and reloaded without browser console errors |
| CAP-01 | Local fictional demo | `self transfer 25k ICICI -> HDFC` at exact 320 CSS px | Pass | Unsaved review showed ₹25,000, ICICI Bank as source, HDFC UPI as destination, `Transfer` category, no horizontal overflow, and explicit `Nothing has been saved yet` copy |

The local transfer was intentionally not confirmed. This checkpoint proves the
parser and review UI only; it does not claim a production database transfer.

## Automated coverage used for currently unexecutable states

The passing web suite covers persisted/auth-state observation, expired/reused
links, wrong-browser PKCE recovery, successful callback handling, expired stored
sessions, retryable reads, retry-safe idempotent confirmation, non-retry of the
unsafe onboarding write, deterministic ₹25k transfer parsing, same-account
validation and theme persistence. The passing API suite covers JWT rejection,
production route behavior, transfer invariants, parser behavior and security
headers.

These tests reduce regression risk but do not replace the hosted authenticated
checks below.

## Checks not run and exact blockers

| ID | Required acceptance | Status | User interaction or external state required |
| --- | --- | --- | --- |
| AUTH-03 | Request and complete a real final-domain magic link in the same browser | Blocked | User must enter a test email and open the newest link in the same browser; the link/code must never be shared in chat |
| AUTH-04 | Refresh, close/reopen tab, close/reopen browser, token refresh and sign-out | Blocked | Requires the authenticated session created by AUTH-03 and the user's browser/email interaction |
| ONB-01 | New user completes onboarding with four fictional banks/accounts, multiple cards and participants | Blocked | Requires authenticated test identity; this run made no production writes |
| ONB-02 | Existing onboarding/profile hydrates after refresh and in a second browser/device | Blocked | Requires completed hosted onboarding plus a second browser sign-in by the same test identity |
| CAP-02 | Production `25k` self-transfer confirms atomically and appears once in history | Blocked | Requires authenticated accounts and explicit confirmation using fictional balances |
| CAP-03 | Production backdated expense and family split | Blocked | Requires authenticated accounts and configured fictional participants |
| RSP-05 | Authenticated Home, onboarding, Quick Add, transactions, shared and assistant at 320/390/desktop in both themes | Blocked | Public sign-in was checked at every requested size/theme; private screens require AUTH-03 |
| NET-01 | Cold and warm authenticated API timings plus visible first-request retry behavior | Blocked | Requires a valid bearer session; anonymous health and denial checks cannot prove authenticated retry UX |
| ISO-01 | Two independent owners cannot read or write each other's household | Blocked | User must provide/control a second test email identity; no passwords, links or tokens should be shared |
| REC-01 | Encrypted export and restore reconstruct the ledger | Blocked | Feature/recovery drill is not complete; this remains a separate release blocker before real data |

## Reliability observation

The command runner's resolver transiently failed to resolve the API hostname
after earlier successful calls. Authoritative DNS lookup still returned both
Vercel edge addresses, and direct TLS requests to each resolved address returned
HTTP 200 in about 64–75 ms. The browser had no production console errors. This
was recorded as an environment-level observation, not as a passed authenticated
reliability check.

## Release decision

The current public and anonymous surface is healthy enough to continue the
private-pilot acceptance. It is **not approved for real financial data** until
AUTH-03/04, ONB-01/02, CAP-02/03, RSP-05, NET-01, ISO-01 and REC-01 are completed
with sanitized evidence.

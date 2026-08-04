# V1 magic-link recovery

Date: 5 August 2026
Status: implemented and verified locally; final-domain acceptance pending

## User-visible states

| Condition | Recovery shown | Next action |
| --- | --- | --- |
| Expired, invalid or already-used link | **This sign-in link has expired** | Request a fresh link and open the newest email in the same browser |
| PKCE code opened in a different browser | **Open the link in the browser that requested it** | Return to the original browser, or request and open a fresh link in the current browser |
| Other incomplete callback | **That sign-in link did not work** | Request a fresh link in the current browser |
| Stored session expired or cannot be restored | **Your session has expired/could not be restored** | Sign in again; the server-owned ledger and setup remain unchanged |
| Missing Supabase deployment configuration | Existing blocking configuration error | Deployment owner must correct the environment |

Recovery states keep the email field enabled and change the primary action to
**Email me a fresh sign-in link**. A successful resend returns to the normal
same-browser instructions. Valid callback sessions continue directly to the
ledger without showing recovery guidance.

## Safety and implementation notes

- Recovery copy never displays Supabase error descriptions, authorization codes,
  tokens or email addresses.
- Authentication callback parameters are removed from the visible URL after they
  have been classified.
- A callback problem never starts onboarding or substitutes demo ledger data.
- Only deployment configuration errors disable sign-in; link and stored-session
  failures remain recoverable by the user.

## Code and tests

- State detection and URL cleanup: `apps/web/src/lib/auth.tsx`
- Accessible recovery UI: `apps/web/src/pages/LoginPage.tsx`
- App integration: `apps/web/src/App.tsx`
- Regression cases: `apps/web/src/lib/auth.test.tsx`

The focused tests cover normal link sending, persisted sessions, expired/reused
links, wrong-browser callbacks, successful callback sessions, PKCE session
errors and expired stored sessions.

## Remaining production acceptance

Use a fictional test identity to verify expired and wrong-browser behavior on the
final domain. Never store the email link, authorization code, token or real user
email in screenshots or logs.

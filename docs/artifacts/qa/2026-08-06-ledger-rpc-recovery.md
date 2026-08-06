# Production ledger RPC recovery

Date: 6 August 2026

## Incident

The authenticated web app failed closed with **Your ledger is temporarily
unavailable**. Public API health stayed green, but the deployed Supabase
PostgREST catalog returned `PGRST202` for `list_ledger_activity`. The web
dashboard and transaction history both depend on that RPC, so the combined
ledger load failed without substituting demo data.

## Root cause and correction

- The deployed web app used Supabase project `vggvufukkkirlwxqkjhz`.
- The local CLI account exposed a different project whose display name looked
  production-like. That project is not the database compiled into the deployed
  web application.
- A migration-history check against that different project therefore did not
  prove anything about the deployed project.
- The deployed PostgREST catalog initially returned `PGRST202` for
  `list_ledger_activity`; a later direct production probe resolved both required
  RPCs and returned the expected anonymous permission denial.
- Release tooling now requires an exact project-ref guard and a direct REST
  catalog probe. A synchronized migration list by itself is not accepted as
  production evidence.

No ledger write, user token, balance or transaction payload was used during the
recovery probe. Authenticated application acceptance remains a separate gate.

## Verification

- Production API `/health`: HTTP `200`.
- Production web root: HTTP `200`.
- Anonymous REST probes for `get_account_balances` and
  `list_ledger_activity`: both functions resolve and reject anonymous access;
  neither returns `PGRST202`/404.
- The probe sends a zero UUID and no user token, balances or transaction data.
- Full local quality gate and authenticated final-domain retry are recorded
  separately when complete.

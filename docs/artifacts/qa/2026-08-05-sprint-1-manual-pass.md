# Sprint 1 manual QA pass

Date: 5 August 2026  
Environment: local Vite application with fictional demo data  
Status: partial pass; hosted auth, narrow viewports and production writes remain blocked

## Executed scenarios

| ID | Scenario | Result | Evidence |
| --- | --- | --- | --- |
| MAN-01 | Dashboard in explicit light theme | Pass | Balances, chart, activity cards and navigation rendered without overlap at desktop width |
| MAN-02 | Dashboard in dark theme | Pass | Dark palette rendered consistently; no light-only transaction form panels observed |
| MAN-03 | `self transfer 25k ICICI -> HDFC` | Pass | Unsaved ₹25,000 transfer with ICICI source, HDFC destination and no split UI |
| MAN-04 | Same source and destination | Pass | Confirm button became disabled |
| MAN-05 | `paid 850 for dinner 3 days ago from HDFC UPI` | Failed, fixed, passed | Date resolved correctly; manual pass found `3 days ago` leaking into description; fixed and retested as description `dinner` |
| MAN-06 | Manual entry | Pass | Editable unsaved form opened with amount/description empty and confirmation disabled |
| MAN-07 | Transfer history filter empty state | Pass | Transfer filter selected, count and net were zero, readable empty state shown |
| MAN-08 | Assistant with provider unavailable | Pass | Clearly labeled deterministic demo fallback; approved metric/insight widgets only |
| MAN-09 | Server-owned onboarding explanation | Failed in review, fixed | Stale “stays on this device” copy replaced with server-ledger persistence explanation |
| MAN-10 | Connectivity vs input error copy | Failed in review, fixed | Timeout/API-unreachable errors now remain connectivity errors and state that nothing was saved |
| MAN-11 | Incomplete transfer destination | Pass | Explicit “Select an account” placeholder, inline guidance and disabled confirmation |

## Not yet executed

- Production magic-link request, callback, refresh, reopen, sign-out and recovery.
- Two-owner hosted RLS isolation.
- Production atomic transfer and history smoke test.
- Real configured-family split in the authenticated ledger.
- 320 px and 390 px manual visual matrix.
- Cold/warm authenticated API measurement after the Mumbai deployment.

These checks require the new commit to be deployed, user-controlled email-link
interaction, a second test identity, or a browser viewport not available in the
current desktop pass. They remain explicit release blockers on the sprint board.

## Automated companion gate

After the manual fixes, the complete local gate passed: 71 web tests, 87 API
tests, strict lint/type checks, a production build and 50 structurally valid
evaluation cases. The web suite includes 22 critical draft cases plus explicit
negative, amount-only and unknown-member safety checks from the shared evaluation dataset.

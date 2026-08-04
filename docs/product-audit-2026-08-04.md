# Artha product audit and priority reset

Date: 4 August 2026  
Status: execution plan for the private pilot

## Product principle

Artha must earn trust before adding breadth. A user should sign in once, resume
the same server-owned ledger on any device, understand every proposed money
movement before it is saved, and know exactly what invited family members can
see. AI may interpret text and propose fields, but it never writes or calculates
ledger truth without deterministic validation and explicit confirmation.

## Prioritized gaps

| Priority | Gap | User impact | Acceptance requirement |
| --- | --- | --- | --- |
| P0 | Session continuity | Repeated login feels like data may be lost | Login survives reload and reopen; callback failures explain same-browser recovery; sign-out is explicit |
| P0 | Server-owned onboarding | Display/household state can differ by device | Profile, household, members and setup status load from Supabase after authentication |
| P0 | Trustworthy capture | Common language such as `25k ICICI -> HDFC` is misread | Structured draft resolves ₹25,000, source, destination, date and transfer semantics before confirmation |
| P0 | Runtime reliability | First request can fail and require retry | API runs in Mumbai beside Supabase; safe reads/idempotent writes retry once; timeout errors are human-readable |
| P0 | Production acceptance | Real money would be premature | Two identities, isolation, mobile/themes, recovery and security checks pass on final URLs |
| P1 | Family invitations | A typed participant cannot log in | Owner can invite, resend, revoke and see invite state without exposing private data |
| P1 | Least-privilege shared view | A family login could otherwise see too much | Invited participant sees only relevant shared expenses, their balance and settlements by default |
| P1 | Post-onboarding management | Accounts and cards cannot be maintained later | Add/edit/archive account metadata and participants; balance corrections remain audited movements |
| P1 | LLM capture evaluation | Model changes can silently regress extraction | Versioned fictional dataset gates amount, date, account, split and ambiguity accuracy |
| P2 | Recovery and workflow polish | Corrections and device loss remain risky | Correction UI, encrypted export/restore, offline drafts and notifications are tested |

## Authentication decision

The login screen represents both first-time account creation and returning login
because Supabase magic-link authentication uses the same action. Product copy
must say this clearly. A returning user must not repeat onboarding; setup state is
looked up on the server. Magic-link completion must either occur in the browser
that requested it or provide a clear recovery path. Password or email-code login
can be added only after its account-recovery and abuse controls are defined.

## Family invitation boundary

There are two different concepts:

1. **Participant:** a name used for expense splits; no login.
2. **Invited user:** an authenticated person linked to a participant after
   accepting an email invitation.

The initial invited-user role is `shared_viewer`. It can read only transactions
where that participant has a split or is the payer, the resulting personal shared
balance, and settlements involving that participant. It cannot read account
balances, unrelated transactions, merchant rules, household analytics or other
members' private activity. Owners can revoke access and every invitation or role
change is audited.

## Execution order

1. Persistent authentication and server-owned profile loading.
2. Transfer/parser and first-request reliability fixes.
3. Final-domain P0 acceptance with two test identities.
4. Versioned invitation schema, RLS policies and limited shared UI.
5. Post-onboarding management and remaining private-pilot improvements.


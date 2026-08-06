# V1 encrypted ledger recovery

Status: implemented and locally accepted on 6 August 2026. Production deployment
and a final-domain drill remain separate release gates.

## User contract

- A signed-in owner downloads one `.artha` file from **Settings → Recovery**.
- The owner supplies a passphrase of at least 12 characters twice.
- Encryption happens in the browser. The passphrase is never sent to Artha,
  stored in browser storage or included in logs.
- Restore appears only before a new account creates a household. The owner first
  decrypts and previews the household name, checksum and record counts, then
  explicitly confirms the atomic restore.
- An existing household cannot be overwritten or merged by V1 restore.

## Data flow

```mermaid
flowchart LR
  DB["Owner household in Postgres"] -->|"owner-only export RPC"| API["FastAPI validation"]
  API -->|"versioned plaintext JSON over TLS"| WEB["Artha PWA"]
  WEB -->|"PBKDF2-SHA-256 + AES-256-GCM"| FILE["Encrypted .artha file"]
  FILE -->|"local passphrase + integrity check"| PREVIEW["Validated restore preview"]
  PREVIEW -->|"explicit confirm + idempotency key"| RESTORE["Atomic restore RPC"]
  RESTORE --> NEWDB["New owner household with new IDs"]
```

## Container and validation

The outer file is a strict, versioned JSON container. It records the KDF and
cipher identifiers, a random 16-byte salt, random 12-byte IV, authenticated
SHA-256 plaintext digest and AES-GCM ciphertext. PBKDF2 uses SHA-256 and 310,000
iterations; encryption uses a 256-bit key and 128-bit authentication tag.

The browser rejects unknown fields, unsupported algorithms, altered work
factors, non-canonical base64, weak passphrases and files over 8 MiB. Wrong
passphrases and ciphertext tampering deliberately share one safe error.

After decryption, FastAPI applies strict Pydantic models and verifies:

- exactly one active owner and participant-only non-owner members;
- unique source IDs and active account/category names;
- closed account, category, member and transaction references;
- exact cashflow split totals;
- matching transfer directions, amounts, currency and timestamps;
- linked settlement/account facts and merchant-rule references;
- timezone-aware event timestamps and bounded collection sizes.

The database RPC remaps every source UUID to a fresh household-scoped UUID in
one transaction. It reconstructs accounts, categories, movements, splits,
transfer pairs, settlements, merchant rules and sanitized audit history. An
idempotency key makes a safe retry return the first result.

## Security boundaries

- Export requires the active household owner; `anon` and `service_role` have no
  direct execute grant on the public recovery RPCs.
- Restore requires an authenticated profile with no active household.
- Email addresses, passwords, access/refresh tokens and provider secrets are
  absent from the bundle.
- Direct hosted acceptance uses protected process environment variables and
  never writes tokens, household IDs or financial rows to evidence.
- Artha cannot recover a forgotten backup passphrase.

## Implementation map

- Browser crypto: `apps/web/src/lib/recovery.ts`
- Recovery UI: `apps/web/src/components/RecoveryPanel.tsx`
- Web API adapter: `apps/web/src/lib/api.ts`
- API validation/routes: `apps/api/src/artha_api/recovery.py` and
  `apps/api/src/artha_api/production_routes.py`
- Database RPCs: `supabase/migrations/20260806030000_encrypted_recovery.sql`
- Round-trip acceptance: `supabase/tests/004_recovery_round_trip.sql`

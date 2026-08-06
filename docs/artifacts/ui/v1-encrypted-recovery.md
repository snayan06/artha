# V1 encrypted recovery UI

Status: implemented and manually checked locally on 6 August 2026.

## Entry points

| State | UI |
| --- | --- |
| Existing ledger owner | Header **Settings** icon → **Recovery** → encrypted download |
| Signed in, no household | First onboarding screen → **Restore an existing Artha ledger** |
| Existing household during restore preview | Restore is blocked without changing data |

The export form requires a passphrase and confirmation. It clears both after a
successful browser download and explains that Artha cannot recover the secret.

The restore flow is intentionally staged:

1. Choose an encrypted `.artha` file and enter its passphrase.
2. Decrypt and verify locally.
3. Ask the authenticated API to validate the complete plaintext bundle.
4. Show household name, checksum prefix and account/transaction/member/transfer
   counts.
5. Require an explicit checkbox before the **Restore ledger** button is enabled.
6. Restore atomically and reload the server-owned onboarding/profile state.

Errors are inline, accessible and non-destructive. The file chooser, inputs,
buttons and checkbox keep at least 44 px interactive targets.

## Responsive and theme evidence

- 320 px onboarding: no horizontal overflow; all recovery controls were 254 px
  wide inside the card and all setup controls remained within the viewport.
- 390 px Settings: recovery heading, passphrase fields, warning and bottom
  navigation remained readable in light and dark themes.
- 1440 × 1000 Settings: no horizontal or vertical overflow; the form uses a
  bounded 3-column-page width and side-by-side passphrase fields.
- Browser console: no warnings or errors during the recovery-page pass.

Automated component coverage verifies weak/mismatched passphrases, encrypted
download, preview-before-write, explicit restore confirmation and the
existing-household blocker.

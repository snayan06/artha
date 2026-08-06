import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const recoveryApi = vi.hoisted(() => ({
  getRecoveryExport: vi.fn(),
  previewRecoveryBundle: vi.fn(),
  restoreRecoveryBundle: vi.fn()
}))
const recoveryCrypto = vi.hoisted(() => ({
  encryptRecoveryBundle: vi.fn(),
  decryptRecoveryBundle: vi.fn()
}))

vi.mock('../lib/api', () => recoveryApi)
vi.mock('../lib/recovery', () => recoveryCrypto)

import { RecoveryExportPanel, RecoveryRestorePanel } from './RecoveryPanel'

const bundle = { format: 'artha-recovery', schema_version: 1 }
const preview = {
  sha256: 'a'.repeat(64), householdName: 'Family ledger', eligible: true, blocker: null,
  counts: { members: 2, accounts: 4, categories: 8, transactions: 42, splits: 10, transfers: 3, settlements: 1, merchantRules: 2, auditEvents: 20 }
}

describe('encrypted recovery UI', () => {
  beforeEach(() => {
    recoveryApi.getRecoveryExport.mockResolvedValue(bundle)
    recoveryApi.previewRecoveryBundle.mockResolvedValue(preview)
    recoveryApi.restoreRecoveryBundle.mockResolvedValue({ householdId: 'household-1', restored: true, idempotentReplay: false, sha256: 'a'.repeat(64) })
    recoveryCrypto.encryptRecoveryBundle.mockResolvedValue('{"encrypted":true}')
    recoveryCrypto.decryptRecoveryBundle.mockResolvedValue(bundle)
    vi.stubGlobal('URL', { ...URL, createObjectURL: vi.fn(() => 'blob:backup'), revokeObjectURL: vi.fn() })
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => undefined)
  })

  afterEach(() => {
    cleanup()
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
    vi.clearAllMocks()
  })

  it('requires matching strong passphrases and downloads only encrypted content', async () => {
    const user = userEvent.setup()
    render(<RecoveryExportPanel />)

    await user.type(screen.getByLabelText('Backup passphrase'), 'short')
    await user.type(screen.getByLabelText('Confirm passphrase'), 'short')
    await user.click(screen.getByRole('button', { name: 'Encrypt and download' }))
    expect(screen.getByRole('alert')).toHaveTextContent('at least 12 characters')
    expect(recoveryApi.getRecoveryExport).not.toHaveBeenCalled()

    await user.clear(screen.getByLabelText('Backup passphrase'))
    await user.clear(screen.getByLabelText('Confirm passphrase'))
    await user.type(screen.getByLabelText('Backup passphrase'), 'a secure passphrase')
    await user.type(screen.getByLabelText('Confirm passphrase'), 'a secure passphrase')
    await user.click(screen.getByRole('button', { name: 'Encrypt and download' }))

    await waitFor(() => expect(recoveryCrypto.encryptRecoveryBundle).toHaveBeenCalledWith(bundle, 'a secure passphrase'))
    expect(screen.getByRole('status')).toHaveTextContent('Encrypted backup downloaded')
    expect(URL.createObjectURL).toHaveBeenCalledWith(expect.any(Blob))
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:backup')
  })

  it('verifies, previews and explicitly confirms a restore before writing', async () => {
    const user = userEvent.setup()
    const onRestored = vi.fn().mockResolvedValue(undefined)
    render(<RecoveryRestorePanel onRestored={onRestored} />)
    const file = new File(['encrypted'], 'ledger.artha', { type: 'application/vnd.artha.encrypted+json' })
    Object.defineProperty(file, 'text', { value: vi.fn().mockResolvedValue('encrypted-container') })

    fireEvent.change(screen.getByLabelText('Encrypted backup'), { target: { files: [file] } })
    await user.type(screen.getByLabelText('Backup passphrase'), 'a secure passphrase')
    await user.click(screen.getByRole('button', { name: 'Verify backup' }))

    expect(await screen.findByText('Family ledger')).toBeInTheDocument()
    expect(screen.getByText('42')).toBeInTheDocument()
    expect(recoveryApi.restoreRecoveryBundle).not.toHaveBeenCalled()
    const restoreButton = screen.getByRole('button', { name: 'Restore ledger' })
    expect(restoreButton).toBeDisabled()

    await user.click(screen.getByRole('checkbox'))
    await user.click(restoreButton)
    await waitFor(() => expect(recoveryApi.restoreRecoveryBundle).toHaveBeenCalledWith(bundle))
    expect(onRestored).toHaveBeenCalledTimes(1)
  })

  it('blocks restore when the signed-in account already has a household', async () => {
    recoveryApi.previewRecoveryBundle.mockResolvedValue({ ...preview, eligible: false, blocker: 'Restore requires a new account with no existing household.' })
    const user = userEvent.setup()
    render(<RecoveryRestorePanel onRestored={vi.fn()} />)
    const file = new File(['encrypted'], 'ledger.artha')
    Object.defineProperty(file, 'text', { value: vi.fn().mockResolvedValue('encrypted-container') })

    fireEvent.change(screen.getByLabelText('Encrypted backup'), { target: { files: [file] } })
    await user.type(screen.getByLabelText('Backup passphrase'), 'a secure passphrase')
    await user.click(screen.getByRole('button', { name: 'Verify backup' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('no existing household')
    expect(screen.getByRole('button', { name: 'Restore ledger' })).toBeDisabled()
  })
})

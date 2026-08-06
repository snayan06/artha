import { webcrypto } from 'node:crypto'
import { beforeAll, describe, expect, it, vi } from 'vitest'
import {
  decryptRecoveryBundle,
  encryptRecoveryBundle,
  MAX_RECOVERY_BUNDLE_BYTES,
  MAX_RECOVERY_CONTAINER_CHARS,
  MIN_RECOVERY_PASSPHRASE_LENGTH,
  RECOVERY_FORMAT,
  RECOVERY_PBKDF2_ITERATIONS,
  RECOVERY_VERSION,
  RecoveryError
} from './recovery'

const passphrase = 'correct horse battery staple'

beforeAll(() => {
  if (!globalThis.crypto?.subtle) {
    Object.defineProperty(globalThis, 'crypto', { configurable: true, value: webcrypto })
  }
})

async function expectRecoveryError(promise: Promise<unknown>, code: RecoveryError['code']): Promise<void> {
  try {
    await promise
    throw new Error('Expected recovery operation to fail')
  } catch (error) {
    expect(error).toBeInstanceOf(RecoveryError)
    expect((error as RecoveryError).code).toBe(code)
  }
}

describe('encrypted recovery bundles', () => {
  it('round-trips a JSON ledger without exposing plaintext', async () => {
    const bundle = {
      schemaVersion: 1,
      household: { name: 'Fictional family' },
      transactions: [{ amountPaise: 2_500_000, description: 'Private transfer 🔒' }]
    }

    const encrypted = await encryptRecoveryBundle(bundle, passphrase)
    const container = JSON.parse(encrypted)

    expect(container).toMatchObject({
      format: RECOVERY_FORMAT,
      version: RECOVERY_VERSION,
      kdf: { name: 'PBKDF2', hash: 'SHA-256', iterations: RECOVERY_PBKDF2_ITERATIONS },
      cipher: { name: 'AES-GCM', keyBits: 256, tagBits: 128 },
      digest: { name: 'SHA-256' }
    })
    expect(encrypted).not.toContain('Fictional family')
    expect(encrypted).not.toContain('Private transfer')
    await expect(decryptRecoveryBundle(encrypted, passphrase)).resolves.toEqual(bundle)
  })

  it('rejects short passphrases before doing cryptographic work', async () => {
    const importKey = vi.spyOn(crypto.subtle, 'importKey')

    await expectRecoveryError(encryptRecoveryBundle({}, 'x'.repeat(MIN_RECOVERY_PASSPHRASE_LENGTH - 1)), 'WEAK_PASSPHRASE')
    await expectRecoveryError(decryptRecoveryBundle('{}', 'too short'), 'WEAK_PASSPHRASE')
    expect(importKey).not.toHaveBeenCalled()
    importKey.mockRestore()
  })

  it('does not distinguish a wrong passphrase from authenticated tampering', async () => {
    const encrypted = await encryptRecoveryBundle({ schemaVersion: 1 }, passphrase)
    await expectRecoveryError(decryptRecoveryBundle(encrypted, 'this is the wrong passphrase'), 'DECRYPTION_FAILED')

    const container = JSON.parse(encrypted)
    const last = container.ciphertext.at(-1)
    container.ciphertext = `${container.ciphertext.slice(0, -1)}${last === 'A' ? 'B' : 'A'}`
    await expectRecoveryError(decryptRecoveryBundle(JSON.stringify(container), passphrase), 'DECRYPTION_FAILED')
  })

  it('verifies the plaintext SHA-256 digest after authenticated decryption', async () => {
    const encrypted = await encryptRecoveryBundle({ schemaVersion: 1 }, passphrase)
    const digest = vi.spyOn(crypto.subtle, 'digest').mockResolvedValue(new Uint8Array(32).buffer)

    await expectRecoveryError(decryptRecoveryBundle(encrypted, passphrase), 'DIGEST_MISMATCH')
    digest.mockRestore()
  })

  it('strictly rejects altered algorithms, work factors, extra fields, and malformed base64 before deriving a key', async () => {
    const encrypted = await encryptRecoveryBundle({ schemaVersion: 1 }, passphrase)
    const original = JSON.parse(encrypted)
    const deriveKey = vi.spyOn(crypto.subtle, 'deriveKey')

    const invalidContainers = [
      { ...original, version: 2 },
      { ...original, extra: true },
      { ...original, kdf: { ...original.kdf, iterations: 9_999_999_999 } },
      { ...original, cipher: { ...original.cipher, name: 'AES-CBC' } },
      { ...original, digest: { ...original.digest, value: 'not base64!' } }
    ]
    for (const invalid of invalidContainers) {
      await expectRecoveryError(decryptRecoveryBundle(JSON.stringify(invalid), passphrase), 'INVALID_CONTAINER')
    }
    expect(deriveKey).not.toHaveBeenCalled()
    deriveKey.mockRestore()
  })

  it('enforces plaintext and pre-parse container size caps', async () => {
    await expectRecoveryError(
      encryptRecoveryBundle({ payload: 'x'.repeat(MAX_RECOVERY_BUNDLE_BYTES) }, passphrase),
      'PAYLOAD_TOO_LARGE'
    )

    const parse = vi.spyOn(JSON, 'parse')
    await expectRecoveryError(
      decryptRecoveryBundle('x'.repeat(MAX_RECOVERY_CONTAINER_CHARS + 1), passphrase),
      'INVALID_CONTAINER'
    )
    expect(parse).not.toHaveBeenCalled()
    parse.mockRestore()
  })

  it('rejects JSON values that cannot be restored faithfully', async () => {
    await expectRecoveryError(
      encryptRecoveryBundle({ unsupported: undefined }, passphrase),
      'INVALID_BUNDLE'
    )
    await expectRecoveryError(
      encryptRecoveryBundle({ amount: Number.POSITIVE_INFINITY }, passphrase),
      'INVALID_BUNDLE'
    )
  })
})

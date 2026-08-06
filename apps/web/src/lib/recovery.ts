const textEncoder = new TextEncoder()
const textDecoder = new TextDecoder('utf-8', { fatal: true })

export const RECOVERY_FORMAT = 'artha-recovery' as const
export const RECOVERY_VERSION = 1 as const
export const RECOVERY_PBKDF2_ITERATIONS = 310_000
export const MIN_RECOVERY_PASSPHRASE_LENGTH = 12
export const MAX_RECOVERY_BUNDLE_BYTES = 8 * 1024 * 1024
export const MAX_RECOVERY_CONTAINER_CHARS = Math.ceil((MAX_RECOVERY_BUNDLE_BYTES + 16) * 4 / 3) + 4_096

const SALT_BYTES = 16
const IV_BYTES = 12
const SHA256_BYTES = 32
const GCM_TAG_BITS = 128
const GCM_TAG_BYTES = GCM_TAG_BITS / 8

export type RecoveryErrorCode =
  | 'WEAK_PASSPHRASE'
  | 'INVALID_BUNDLE'
  | 'INVALID_CONTAINER'
  | 'PAYLOAD_TOO_LARGE'
  | 'DECRYPTION_FAILED'
  | 'DIGEST_MISMATCH'

export class RecoveryError extends Error {
  readonly code: RecoveryErrorCode

  constructor(code: RecoveryErrorCode, message: string) {
    super(message)
    this.name = 'RecoveryError'
    this.code = code
  }
}

interface RecoveryContainer {
  format: typeof RECOVERY_FORMAT
  version: typeof RECOVERY_VERSION
  kdf: {
    name: 'PBKDF2'
    hash: 'SHA-256'
    iterations: typeof RECOVERY_PBKDF2_ITERATIONS
    salt: string
  }
  cipher: {
    name: 'AES-GCM'
    keyBits: 256
    tagBits: typeof GCM_TAG_BITS
    iv: string
  }
  digest: {
    name: 'SHA-256'
    value: string
  }
  ciphertext: string
}

function fail(code: RecoveryErrorCode, message: string): never {
  throw new RecoveryError(code, message)
}

function assertPassphrase(passphrase: string): void {
  if (typeof passphrase !== 'string' || [...passphrase].length < MIN_RECOVERY_PASSPHRASE_LENGTH) {
    fail('WEAK_PASSPHRASE', `Recovery passphrase must be at least ${MIN_RECOVERY_PASSPHRASE_LENGTH} characters.`)
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function hasExactKeys(value: Record<string, unknown>, keys: readonly string[]): boolean {
  const actual = Object.keys(value).sort()
  const expected = [...keys].sort()
  return actual.length === expected.length && actual.every((key, index) => key === expected[index])
}

function encodeBase64(bytes: Uint8Array): string {
  const chunks: string[] = []
  const chunkSize = 0x8000
  for (let offset = 0; offset < bytes.length; offset += chunkSize) {
    chunks.push(String.fromCharCode(...bytes.subarray(offset, offset + chunkSize)))
  }
  return btoa(chunks.join(''))
}

function decodeBase64(value: unknown, label: string, expectedBytes?: number): Uint8Array {
  if (typeof value !== 'string' || value.length === 0 || value.length > MAX_RECOVERY_CONTAINER_CHARS) {
    fail('INVALID_CONTAINER', `${label} is not a valid encoded value.`)
  }
  if (!/^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$/.test(value)) {
    fail('INVALID_CONTAINER', `${label} is not canonical base64.`)
  }
  let binary: string
  try {
    binary = atob(value)
  } catch {
    fail('INVALID_CONTAINER', `${label} is not valid base64.`)
  }
  const bytes = new Uint8Array(binary.length)
  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index)
  }
  if (expectedBytes !== undefined && bytes.length !== expectedBytes) {
    fail('INVALID_CONTAINER', `${label} has an invalid length.`)
  }
  if (encodeBase64(bytes) !== value) {
    fail('INVALID_CONTAINER', `${label} is not canonical base64.`)
  }
  return bytes
}

function parseContainer(text: string): { container: RecoveryContainer; salt: Uint8Array; iv: Uint8Array; digest: Uint8Array; ciphertext: Uint8Array } {
  if (typeof text !== 'string' || text.length === 0 || text.length > MAX_RECOVERY_CONTAINER_CHARS) {
    fail('INVALID_CONTAINER', 'Recovery file is empty or exceeds the supported size.')
  }

  let parsed: unknown
  try {
    parsed = JSON.parse(text)
  } catch {
    fail('INVALID_CONTAINER', 'Recovery file is not valid JSON.')
  }
  if (!isRecord(parsed) || !hasExactKeys(parsed, ['format', 'version', 'kdf', 'cipher', 'digest', 'ciphertext'])) {
    fail('INVALID_CONTAINER', 'Recovery file has an invalid container shape.')
  }
  if (parsed.format !== RECOVERY_FORMAT || parsed.version !== RECOVERY_VERSION) {
    fail('INVALID_CONTAINER', 'Recovery file format or version is not supported.')
  }
  if (!isRecord(parsed.kdf) || !hasExactKeys(parsed.kdf, ['name', 'hash', 'iterations', 'salt'])) {
    fail('INVALID_CONTAINER', 'Recovery file has invalid key-derivation settings.')
  }
  if (
    parsed.kdf.name !== 'PBKDF2'
    || parsed.kdf.hash !== 'SHA-256'
    || parsed.kdf.iterations !== RECOVERY_PBKDF2_ITERATIONS
  ) {
    fail('INVALID_CONTAINER', 'Recovery file uses unsupported key-derivation settings.')
  }
  if (!isRecord(parsed.cipher) || !hasExactKeys(parsed.cipher, ['name', 'keyBits', 'tagBits', 'iv'])) {
    fail('INVALID_CONTAINER', 'Recovery file has invalid cipher settings.')
  }
  if (parsed.cipher.name !== 'AES-GCM' || parsed.cipher.keyBits !== 256 || parsed.cipher.tagBits !== GCM_TAG_BITS) {
    fail('INVALID_CONTAINER', 'Recovery file uses unsupported cipher settings.')
  }
  if (!isRecord(parsed.digest) || !hasExactKeys(parsed.digest, ['name', 'value']) || parsed.digest.name !== 'SHA-256') {
    fail('INVALID_CONTAINER', 'Recovery file has invalid digest settings.')
  }

  const salt = decodeBase64(parsed.kdf.salt, 'Salt', SALT_BYTES)
  const iv = decodeBase64(parsed.cipher.iv, 'Initialization vector', IV_BYTES)
  const digest = decodeBase64(parsed.digest.value, 'Payload digest', SHA256_BYTES)
  const ciphertext = decodeBase64(parsed.ciphertext, 'Ciphertext')
  if (ciphertext.length < GCM_TAG_BYTES || ciphertext.length > MAX_RECOVERY_BUNDLE_BYTES + GCM_TAG_BYTES) {
    fail('INVALID_CONTAINER', 'Ciphertext has an invalid length.')
  }

  return { container: parsed as unknown as RecoveryContainer, salt, iv, digest, ciphertext }
}

function authenticatedHeader(container: RecoveryContainer): Uint8Array {
  return textEncoder.encode(JSON.stringify({
    format: container.format,
    version: container.version,
    kdf: container.kdf,
    cipher: container.cipher,
    digest: container.digest
  }))
}

function ownedArrayBuffer(bytes: Uint8Array): ArrayBuffer {
  const owned = new Uint8Array(bytes.byteLength)
  owned.set(bytes)
  return owned.buffer
}

async function deriveKey(passphrase: string, salt: Uint8Array): Promise<CryptoKey> {
  const keyMaterial = await crypto.subtle.importKey(
    'raw',
    textEncoder.encode(passphrase),
    'PBKDF2',
    false,
    ['deriveKey']
  )
  return crypto.subtle.deriveKey(
    {
      name: 'PBKDF2',
      hash: 'SHA-256',
      salt: ownedArrayBuffer(salt),
      iterations: RECOVERY_PBKDF2_ITERATIONS
    },
    keyMaterial,
    { name: 'AES-GCM', length: 256 },
    false,
    ['encrypt', 'decrypt']
  )
}

function serializeBundle(bundle: Record<string, unknown>): Uint8Array {
  if (!isRecord(bundle)) {
    fail('INVALID_BUNDLE', 'Recovery bundle must be a JSON object.')
  }
  let serialized: string | undefined
  try {
    serialized = JSON.stringify(bundle, (_key, value: unknown) => {
      if (value === undefined || typeof value === 'function' || typeof value === 'symbol' || typeof value === 'bigint') {
        fail('INVALID_BUNDLE', 'Recovery bundle contains a value that JSON cannot preserve.')
      }
      if (typeof value === 'number' && !Number.isFinite(value)) {
        fail('INVALID_BUNDLE', 'Recovery bundle contains a non-finite number.')
      }
      return value
    })
  } catch (error) {
    if (error instanceof RecoveryError) throw error
    fail('INVALID_BUNDLE', 'Recovery bundle cannot be serialized safely.')
  }
  if (serialized === undefined) {
    fail('INVALID_BUNDLE', 'Recovery bundle cannot be serialized safely.')
  }
  const plaintext = textEncoder.encode(serialized)
  if (plaintext.length > MAX_RECOVERY_BUNDLE_BYTES) {
    fail('PAYLOAD_TOO_LARGE', 'Recovery bundle exceeds the supported size.')
  }
  return plaintext
}

function digestsEqual(left: Uint8Array, right: Uint8Array): boolean {
  if (left.length !== right.length) return false
  let difference = 0
  for (let index = 0; index < left.length; index += 1) {
    difference |= left[index] ^ right[index]
  }
  return difference === 0
}

export async function encryptRecoveryBundle(bundle: Record<string, unknown>, passphrase: string): Promise<string> {
  assertPassphrase(passphrase)
  const plaintext = serializeBundle(bundle)
  const salt = crypto.getRandomValues(new Uint8Array(SALT_BYTES))
  const iv = crypto.getRandomValues(new Uint8Array(IV_BYTES))
  const digest = new Uint8Array(await crypto.subtle.digest('SHA-256', ownedArrayBuffer(plaintext)))
  const container: RecoveryContainer = {
    format: RECOVERY_FORMAT,
    version: RECOVERY_VERSION,
    kdf: {
      name: 'PBKDF2',
      hash: 'SHA-256',
      iterations: RECOVERY_PBKDF2_ITERATIONS,
      salt: encodeBase64(salt)
    },
    cipher: {
      name: 'AES-GCM',
      keyBits: 256,
      tagBits: GCM_TAG_BITS,
      iv: encodeBase64(iv)
    },
    digest: { name: 'SHA-256', value: encodeBase64(digest) },
    ciphertext: ''
  }
  const key = await deriveKey(passphrase, salt)
  const encrypted = await crypto.subtle.encrypt(
    {
      name: 'AES-GCM',
      iv: ownedArrayBuffer(iv),
      additionalData: ownedArrayBuffer(authenticatedHeader(container)),
      tagLength: GCM_TAG_BITS
    },
    key,
    ownedArrayBuffer(plaintext)
  )
  container.ciphertext = encodeBase64(new Uint8Array(encrypted))
  return JSON.stringify(container)
}

export async function decryptRecoveryBundle(text: string, passphrase: string): Promise<Record<string, unknown>> {
  assertPassphrase(passphrase)
  const { container, salt, iv, digest, ciphertext } = parseContainer(text)
  const key = await deriveKey(passphrase, salt)
  let plaintextBuffer: ArrayBuffer
  try {
    plaintextBuffer = await crypto.subtle.decrypt(
      {
        name: 'AES-GCM',
        iv: ownedArrayBuffer(iv),
        additionalData: ownedArrayBuffer(authenticatedHeader(container)),
        tagLength: GCM_TAG_BITS
      },
      key,
      ownedArrayBuffer(ciphertext)
    )
  } catch {
    fail('DECRYPTION_FAILED', 'Recovery file could not be decrypted with this passphrase.')
  }
  const plaintext = new Uint8Array(plaintextBuffer)
  if (plaintext.length > MAX_RECOVERY_BUNDLE_BYTES) {
    fail('PAYLOAD_TOO_LARGE', 'Decrypted recovery bundle exceeds the supported size.')
  }
  const actualDigest = new Uint8Array(
    await crypto.subtle.digest('SHA-256', ownedArrayBuffer(plaintext))
  )
  if (!digestsEqual(actualDigest, digest)) {
    fail('DIGEST_MISMATCH', 'Recovery bundle failed its integrity check.')
  }

  let bundle: unknown
  try {
    bundle = JSON.parse(textDecoder.decode(plaintext))
  } catch {
    fail('INVALID_BUNDLE', 'Decrypted recovery bundle is not valid JSON.')
  }
  if (!isRecord(bundle)) {
    fail('INVALID_BUNDLE', 'Decrypted recovery bundle must be a JSON object.')
  }
  return bundle
}

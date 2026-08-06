import { CheckCircle2, Download, FileKey2, ShieldCheck, Upload } from 'lucide-react'
import { useRef, useState } from 'react'
import { getRecoveryExport, previewRecoveryBundle, restoreRecoveryBundle, type RecoveryBundle, type RecoverySummary } from '../lib/api'
import { decryptRecoveryBundle, encryptRecoveryBundle } from '../lib/recovery'
import { Button, Card } from './ui'

const PASSPHRASE_HINT = 'Use at least 12 characters. Artha cannot recover this passphrase.'

function RecoveryField({ label, value, onChange, placeholder }: { label: string; value: string; onChange: (value: string) => void; placeholder: string }) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-[11px] font-semibold uppercase tracking-[0.1em] text-[#6f7d76] tone-muted">{label}</span>
      <input type="password" autoComplete="new-password" value={value} onChange={(event) => onChange(event.target.value)} placeholder={placeholder} className="min-h-12 w-full rounded-xl border border-line bg-white px-3 text-base outline-none transition focus-visible:border-moss-400 focus-visible:ring-4 focus-visible:ring-moss-100 dark:border-night-border dark:bg-night-raised" />
    </label>
  )
}

export function RecoveryExportPanel() {
  const [passphrase, setPassphrase] = useState('')
  const [confirmPassphrase, setConfirmPassphrase] = useState('')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  async function downloadBackup() {
    setError('')
    setMessage('')
    if (passphrase.length < 12) return setError(PASSPHRASE_HINT)
    if (passphrase !== confirmPassphrase) return setError('The two passphrases do not match.')
    setBusy(true)
    try {
      const bundle = await getRecoveryExport()
      const encrypted = await encryptRecoveryBundle(bundle, passphrase)
      const url = URL.createObjectURL(new Blob([encrypted], { type: 'application/vnd.artha.encrypted+json' }))
      const link = document.createElement('a')
      link.href = url
      link.download = `artha-backup-${new Date().toISOString().slice(0, 10)}.artha`
      link.click()
      URL.revokeObjectURL(url)
      setPassphrase('')
      setConfirmPassphrase('')
      setMessage('Encrypted backup downloaded. Store the file and passphrase separately.')
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'The backup could not be created. Nothing was changed.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card className="p-4 sm:p-6">
      <div className="flex items-start gap-3">
        <span className="grid h-11 w-11 shrink-0 place-items-center rounded-2xl bg-moss-100 text-moss-800"><Download className="h-5 w-5" aria-hidden="true" /></span>
        <div><h2 className="font-display text-lg font-bold">Download encrypted backup</h2><p className="mt-1 text-sm leading-6 text-[#66746d] tone-muted">Includes your ledger, accounts, household members and rules. Your password and sign-in token are never included.</p></div>
      </div>
      <div className="mt-5 grid gap-4 sm:grid-cols-2">
        <RecoveryField label="Backup passphrase" value={passphrase} onChange={setPassphrase} placeholder="At least 12 characters" />
        <RecoveryField label="Confirm passphrase" value={confirmPassphrase} onChange={setConfirmPassphrase} placeholder="Type it again" />
      </div>
      <p className="mt-2 text-xs leading-5 text-[#748079] tone-muted">{PASSPHRASE_HINT}</p>
      {error && <p role="alert" className="mt-4 rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-800 dark:border-red-900 dark:bg-red-950/40 dark:text-red-200">{error}</p>}
      {message && <p role="status" className="mt-4 flex items-start gap-2 rounded-xl border border-moss-200 bg-moss-50 p-3 text-sm text-moss-900 dark:border-night-border dark:bg-night-raised"><CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />{message}</p>}
      <Button loading={busy} onClick={() => void downloadBackup()} className="mt-5 w-full sm:w-auto" icon={<FileKey2 className="h-4 w-4" aria-hidden="true" />}>Encrypt and download</Button>
    </Card>
  )
}

export function RecoveryRestorePanel({ onRestored }: { onRestored: () => Promise<void> }) {
  const fileRef = useRef<HTMLInputElement>(null)
  const [file, setFile] = useState<File | null>(null)
  const [passphrase, setPassphrase] = useState('')
  const [bundle, setBundle] = useState<RecoveryBundle | null>(null)
  const [summary, setSummary] = useState<RecoverySummary | null>(null)
  const [confirmed, setConfirmed] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  function resetPreview() {
    setBundle(null)
    setSummary(null)
    setConfirmed(false)
    setError('')
  }

  async function inspectBackup() {
    setError('')
    if (!file) return setError('Choose an Artha backup file first.')
    if (!passphrase) return setError('Enter the backup passphrase.')
    setBusy(true)
    try {
      const decrypted = await decryptRecoveryBundle(await file.text(), passphrase)
      const preview = await previewRecoveryBundle(decrypted)
      setBundle(decrypted)
      setSummary(preview)
      setConfirmed(false)
      setPassphrase('')
    } catch (caught) {
      resetPreview()
      setError(caught instanceof Error ? caught.message : 'The backup could not be opened. Check the file and passphrase.')
    } finally {
      setBusy(false)
    }
  }

  async function restore() {
    if (!bundle || !summary?.eligible || !confirmed) return
    setBusy(true)
    setError('')
    try {
      const result = await restoreRecoveryBundle(bundle)
      if (!result.restored && !result.idempotentReplay) throw new Error('Artha could not confirm the restore.')
      setBundle(null)
      setSummary(null)
      setFile(null)
      setConfirmed(false)
      if (fileRef.current) fileRef.current.value = ''
      await onRestored()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Restore failed safely. No partial ledger was kept.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card className="p-4 sm:p-6">
      <div className="flex items-start gap-3">
        <span className="grid h-11 w-11 shrink-0 place-items-center rounded-2xl bg-moss-100 text-moss-800"><Upload className="h-5 w-5" aria-hidden="true" /></span>
        <div><h2 className="font-display text-lg font-bold">Restore an existing Artha ledger</h2><p className="mt-1 text-sm leading-6 text-[#66746d] tone-muted">Use this instead of creating new opening balances. Artha checks the complete backup before writing anything.</p></div>
      </div>
      {!summary && (
        <div className="mt-5 grid gap-4 sm:grid-cols-2">
          <label className="block"><span className="mb-1.5 block text-[11px] font-semibold uppercase tracking-[0.1em] text-[#6f7d76] tone-muted">Encrypted backup</span><input ref={fileRef} type="file" accept=".artha,application/json,application/vnd.artha.encrypted+json" onChange={(event) => { setFile(event.target.files?.[0] ?? null); resetPreview() }} className="block min-h-12 w-full rounded-xl border border-line bg-white p-2 text-sm file:mr-3 file:rounded-lg file:border-0 file:bg-moss-100 file:px-3 file:py-2 file:font-semibold file:text-moss-900 dark:border-night-border dark:bg-night-raised" /></label>
          <RecoveryField label="Backup passphrase" value={passphrase} onChange={(value) => { setPassphrase(value); resetPreview() }} placeholder="Your backup passphrase" />
        </div>
      )}
      {summary && (
        <div className="mt-5 rounded-2xl border border-line bg-[#f8faf7] p-4 dark:border-night-border dark:bg-night-raised">
          <div className="flex items-start gap-2"><ShieldCheck className="mt-0.5 h-5 w-5 shrink-0 text-moss-700" aria-hidden="true" /><div><p className="font-semibold">{summary.householdName}</p><p className="mt-1 break-all text-xs text-[#6f7d76] tone-muted">Verified backup · {summary.sha256.slice(0, 16)}…</p></div></div>
          <dl className="mt-4 grid grid-cols-2 gap-3 text-sm sm:grid-cols-4"><Count label="Accounts" value={summary.counts.accounts} /><Count label="Transactions" value={summary.counts.transactions} /><Count label="Members" value={summary.counts.members} /><Count label="Transfers" value={summary.counts.transfers} /></dl>
          {summary.blocker && <p role="alert" className="mt-4 rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-100">{summary.blocker}</p>}
          {summary.eligible && <label className="mt-4 flex min-h-11 cursor-pointer items-start gap-3 rounded-xl border border-line bg-white p-3 text-sm dark:border-night-border dark:bg-night-surface"><input type="checkbox" checked={confirmed} onChange={(event) => setConfirmed(event.target.checked)} className="mt-0.5 h-5 w-5 accent-moss-800" /><span>I reviewed this summary. Restore it into this empty account.</span></label>}
        </div>
      )}
      {error && <p role="alert" className="mt-4 rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-800 dark:border-red-900 dark:bg-red-950/40 dark:text-red-200">{error}</p>}
      <div className="mt-5 flex flex-col gap-3 sm:flex-row">
        {!summary ? <Button loading={busy} onClick={() => void inspectBackup()} icon={<FileKey2 className="h-4 w-4" aria-hidden="true" />}>Verify backup</Button> : <Button loading={busy} disabled={!summary.eligible || !confirmed} onClick={() => void restore()} icon={<Upload className="h-4 w-4" aria-hidden="true" />}>Restore ledger</Button>}
        {summary && <Button variant="secondary" disabled={busy} onClick={() => { resetPreview(); setFile(null); if (fileRef.current) fileRef.current.value = '' }}>Choose another file</Button>}
      </div>
    </Card>
  )
}

function Count({ label, value }: { label: string; value: number }) {
  return <div><dt className="text-xs text-[#748079] tone-muted">{label}</dt><dd className="mt-1 font-display text-xl font-bold">{value.toLocaleString('en-IN')}</dd></div>
}

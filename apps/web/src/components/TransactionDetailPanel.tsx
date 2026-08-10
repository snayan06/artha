import { AlertTriangle, Pencil, Trash2, X } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Button } from './ui'
import { formatMoney, rupeesToPaise } from '../lib/money'
import { useModalSafety } from '../lib/useModalSafety'
import type { CaptureCategory, LedgerAccount, Transaction, TransactionDraft } from '../types'

type Mode = 'view' | 'edit' | 'remove'
const noAccounts: LedgerAccount[] = []
const noCategories: CaptureCategory[] = []

export function TransactionDetailPanel({
  transaction,
  accounts = noAccounts,
  categories = noCategories,
  onClose,
  onUpdate,
  onVoid
}: {
  transaction: Transaction
  accounts?: LedgerAccount[]
  categories?: CaptureCategory[]
  onClose: () => void
  onUpdate?: (id: string, draft: TransactionDraft, reason: string) => Promise<void>
  onVoid?: (id: string, reason: string) => Promise<void>
}) {
  const editable = transaction.kind === 'debit' || transaction.kind === 'credit' || transaction.kind === 'transfer'
  const initialSourceAccountId = String(transaction.sourceAccountId ?? accounts.find((account) => account.name.localeCompare(transaction.account, undefined, { sensitivity: 'accent' }) === 0)?.id ?? '')
  const initialDestinationAccountId = String(transaction.destinationAccountId ?? accounts.find((account) => account.name.localeCompare(transaction.destinationAccount ?? '', undefined, { sensitivity: 'accent' }) === 0)?.id ?? '')
  const [mode, setMode] = useState<Mode>('view')
  const [amount, setAmount] = useState(String(transaction.amountPaise / 100))
  const [description, setDescription] = useState(transaction.merchant)
  const [occurredAt, setOccurredAt] = useState(transaction.occurredAt)
  const [note, setNote] = useState(transaction.note ?? '')
  const [category, setCategory] = useState(transaction.category)
  const [sourceAccountId, setSourceAccountId] = useState(initialSourceAccountId)
  const [destinationAccountId, setDestinationAccountId] = useState(initialDestinationAccountId)
  const [splitAmounts, setSplitAmounts] = useState<Record<string, string>>(() => Object.fromEntries(transaction.memberSplits.map((split) => [split.memberId, String(split.amountPaise / 100)])))
  const [reason, setReason] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const dialogRef = useRef<HTMLElement>(null)
  useModalSafety(dialogRef, onClose)

  useEffect(() => {
    setMode('view')
    setAmount(String(transaction.amountPaise / 100))
    setDescription(transaction.merchant)
    setOccurredAt(transaction.occurredAt)
    setNote(transaction.note ?? '')
    setCategory(transaction.category)
    setSourceAccountId(initialSourceAccountId)
    setDestinationAccountId(initialDestinationAccountId)
    setSplitAmounts(Object.fromEntries(transaction.memberSplits.map((split) => [split.memberId, String(split.amountPaise / 100)])))
    setReason('')
    setError('')
  }, [initialDestinationAccountId, initialSourceAccountId, transaction])

  async function saveCorrection() {
    const correctionKind = transaction.kind === 'debit' || transaction.kind === 'credit' || transaction.kind === 'transfer' ? transaction.kind : null
    if (!correctionKind || !onUpdate || saving || !reason.trim()) return
    const amountPaise = rupeesToPaise(Number(amount))
    if (amountPaise <= 0 || !description.trim() || !occurredAt) return
    const memberSplits = transaction.memberSplits.map((split) => ({ ...split, amountPaise: rupeesToPaise(Number(splitAmounts[split.memberId] ?? 0)) }))
    const sourceAccount = accounts.find((account) => String(account.id) === sourceAccountId)
    const destinationAccount = accounts.find((account) => String(account.id) === destinationAccountId)
    const draft: TransactionDraft = {
      kind: correctionKind,
      amountPaise,
      merchant: description.trim(),
      category: transaction.kind === 'transfer' ? 'Transfer' : category,
      account: sourceAccount?.name ?? transaction.account,
      sourceAccountId: sourceAccount?.id ?? transaction.sourceAccountId,
      destinationAccount: destinationAccount?.name ?? transaction.destinationAccount,
      destinationAccountId: destinationAccount?.id ?? transaction.destinationAccountId,
      occurredAt,
      note: note.trim(),
      memberSplits,
      confidence: 'review',
      sourceText: ''
    }
    setSaving(true)
    setError('')
    try {
      await onUpdate(transaction.id, draft, reason.trim())
      setMode('view')
      setReason('')
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'The correction was not saved. Please try again.')
    } finally {
      setSaving(false)
    }
  }

  async function removeTransaction() {
    if (!onVoid || saving || !reason.trim()) return
    setSaving(true)
    setError('')
    try {
      await onVoid(transaction.id, reason.trim())
      onClose()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'The transaction was not removed. Please try again.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 grid items-end bg-black/35 p-0 sm:place-items-center sm:p-6" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose() }}>
      <section ref={dialogRef} role="dialog" aria-modal="true" aria-label="Transaction details" className="max-h-[92svh] w-full overflow-y-auto rounded-t-[28px] border border-line bg-white p-5 shadow-2xl sm:max-w-lg sm:rounded-[28px] sm:p-6 dark:border-night-border dark:bg-night-surface">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.12em] text-moss-700">Transaction details</p>
            <h2 id="transaction-detail-title" className="font-display mt-1 text-2xl font-bold tracking-[-0.04em]">{transaction.merchant}</h2>
          </div>
          <button onClick={onClose} className="grid h-11 w-11 shrink-0 place-items-center rounded-xl text-[#65726b] hover:bg-moss-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-moss-400" aria-label="Close transaction details"><X className="h-5 w-5" aria-hidden="true" /></button>
        </div>

        {mode === 'view' && (
          <>
            <p className="font-display mt-6 text-4xl font-bold tracking-[-0.05em]">{formatMoney(transaction.amountPaise)}</p>
            <dl className="mt-6 grid gap-4 rounded-2xl bg-[#f5f7f4] p-4 text-sm dark:bg-night-raised sm:grid-cols-2">
              <Detail label="Type" value={transaction.kind === 'debit' ? 'Expense' : transaction.kind === 'credit' ? 'Income' : transaction.kind === 'transfer' ? 'Transfer' : transaction.kind === 'settlement' ? 'Shared repayment' : 'Balance correction'} />
              <Detail label="Date" value={new Intl.DateTimeFormat('en-IN', { day: 'numeric', month: 'short', year: 'numeric' }).format(new Date(`${transaction.occurredAt}T12:00:00`))} />
              <Detail label={transaction.kind === 'transfer' ? 'From' : 'Account'} value={transaction.account} />
              {transaction.destinationAccount && <Detail label="To" value={transaction.destinationAccount} />}
              <Detail label="Category" value={transaction.category} />
              {editable && <Detail label="Your share" value={formatMoney(transaction.personalSharePaise)} />}
            </dl>
            {transaction.memberSplits.length > 0 && <p className="mt-4 text-sm text-[#66736d] tone-muted">Shared with {transaction.memberSplits.map((split) => split.memberName).join(', ')}.</p>}
            {transaction.note && <p className="mt-4 rounded-2xl bg-[#f5f7f4] p-4 text-sm text-[#66736d] dark:bg-night-raised"><strong className="text-ink">Note:</strong> {transaction.note}</p>}
            {editable && <div className="mt-7 grid gap-3 sm:grid-cols-2">
              <Button variant="secondary" onClick={() => { setMode('edit'); setReason('') }} icon={<Pencil className="h-4 w-4" aria-hidden="true" />}>Edit transaction</Button>
              <Button variant="secondary" onClick={() => { setMode('remove'); setReason('') }} icon={<Trash2 className="h-4 w-4" aria-hidden="true" />}>Remove from totals</Button>
            </div>}
          </>
        )}

        {mode === 'edit' && (
          <div className="mt-6 grid gap-4">
            <p className="rounded-2xl bg-moss-50 p-3 text-sm text-moss-900 dark:bg-night-raised dark:text-night-ink">Artha keeps the original in your audit history and posts this reviewed replacement atomically.</p>
            <Field label="Amount in rupees" type="number" value={amount} onChange={setAmount} />
            <Field label="Description" value={description} onChange={setDescription} />
            {accounts.length > 0 && <SelectField label={transaction.kind === 'transfer' ? 'From account' : 'Account'} value={sourceAccountId} onChange={setSourceAccountId} options={accounts.map((account) => ({ value: String(account.id), label: account.name }))} />}
            {transaction.kind === 'transfer' && accounts.length > 0 && <SelectField label="To account" value={destinationAccountId} onChange={setDestinationAccountId} options={accounts.filter((account) => String(account.id) !== sourceAccountId).map((account) => ({ value: String(account.id), label: account.name }))} />}
            {transaction.kind !== 'transfer' && categories.length > 0 && <SelectField label="Category" value={category} onChange={setCategory} options={categories.filter((item) => item.kind === (transaction.kind === 'credit' ? 'income' : 'expense') || item.kind === 'both').map((item) => ({ value: item.name, label: item.name }))} />}
            <Field label="Transaction date" type="date" value={occurredAt} onChange={setOccurredAt} />
            <Field label="Note (optional)" value={note} onChange={setNote} />
            {transaction.memberSplits.map((split) => <Field key={split.memberId} label={`${split.memberName}'s share in rupees`} type="number" value={splitAmounts[split.memberId] ?? ''} onChange={(value) => setSplitAmounts((current) => ({ ...current, [split.memberId]: value }))} />)}
            <Field label="Why are you correcting this?" value={reason} onChange={setReason} />
            {error && <p role="alert" className="rounded-xl bg-red-50 p-3 text-sm text-red-800">{error}</p>}
            <div className="grid gap-3 sm:grid-cols-2">
              <Button variant="secondary" onClick={() => setMode('view')}>Cancel</Button>
              <Button loading={saving} disabled={!reason.trim() || !description.trim() || rupeesToPaise(Number(amount)) <= 0 || Object.values(splitAmounts).reduce((sum, value) => sum + rupeesToPaise(Number(value)), 0) > rupeesToPaise(Number(amount)) || (transaction.kind === 'transfer' && sourceAccountId === destinationAccountId)} onClick={() => void saveCorrection()}>Save correction</Button>
            </div>
          </div>
        )}

        {mode === 'remove' && (
          <div className="mt-6 grid gap-4">
            <div className="flex gap-3 rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900"><AlertTriangle className="h-5 w-5 shrink-0" aria-hidden="true" /><p>This removes the transaction from balances and totals. The original remains in the audit history.</p></div>
            <Field label="Why are you removing this?" value={reason} onChange={setReason} />
            {error && <p role="alert" className="rounded-xl bg-red-50 p-3 text-sm text-red-800">{error}</p>}
            <div className="grid gap-3 sm:grid-cols-2">
              <Button variant="secondary" onClick={() => setMode('view')}>Keep transaction</Button>
              <Button loading={saving} disabled={!reason.trim()} onClick={() => void removeTransaction()}>Confirm removal</Button>
            </div>
          </div>
        )}
      </section>
    </div>
  )
}

function Detail({ label, value }: { label: string; value: string }) {
  return <div><dt className="text-xs font-semibold uppercase tracking-[0.08em] text-[#7b8781] tone-muted">{label}</dt><dd className="mt-1 font-semibold text-ink">{value}</dd></div>
}

function Field({ label, value, onChange, type = 'text' }: { label: string; value: string; onChange: (value: string) => void; type?: 'text' | 'number' | 'date' }) {
  return <label className="grid gap-1.5 text-sm font-semibold text-ink">{label}<input aria-label={label} type={type} inputMode={type === 'number' ? 'decimal' : undefined} value={value} onChange={(event) => onChange(event.target.value)} className="min-h-12 rounded-xl border border-line bg-white px-3 text-sm outline-none focus-visible:border-moss-400 focus-visible:ring-4 focus-visible:ring-moss-100 dark:bg-night-input" /></label>
}

function SelectField({ label, value, onChange, options }: { label: string; value: string; onChange: (value: string) => void; options: Array<{ value: string; label: string }> }) {
  return <label className="grid gap-1.5 text-sm font-semibold text-ink">{label}<select aria-label={label} value={value} onChange={(event) => onChange(event.target.value)} className="min-h-12 rounded-xl border border-line bg-white px-3 text-sm outline-none focus-visible:border-moss-400 focus-visible:ring-4 focus-visible:ring-moss-100 dark:bg-night-input"><option value="">Choose an option</option>{options.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select></label>
}

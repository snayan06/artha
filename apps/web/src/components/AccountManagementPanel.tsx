import { useEffect, useState, type FormEvent } from 'react'
import { createManagedAccount, getManagedAccounts, reconcileAccountBalance, setManagedAccountArchived, updateManagedAccount } from '../lib/api'
import { formatMoney, rupeesToPaise } from '../lib/money'
import type { EntityId, ManagedAccount } from '../types'

export function AccountManagementPanel() {
  const [accounts, setAccounts] = useState<ManagedAccount[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [editingId, setEditingId] = useState<EntityId | null>(null)
  const [actual, setActual] = useState('')
  const [reason, setReason] = useState('Statement reconciliation')
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10))
  const [saving, setSaving] = useState(false)
  const [showAdd, setShowAdd] = useState(false)
  const [manageId, setManageId] = useState<EntityId | null>(null)

  async function load() {
    setLoading(true)
    setError('')
    try { setAccounts(await getManagedAccounts()) } catch { setError('Artha could not load your accounts. Please try again.') } finally { setLoading(false) }
  }

  useEffect(() => { void load() }, [])

  function begin(account: ManagedAccount) {
    setEditingId(account.id)
    setActual(String(account.currentBalancePaise / 100))
    setReason('Statement reconciliation')
    setError('')
  }

  async function submit(event: FormEvent, account: ManagedAccount) {
    event.preventDefault()
    if (!reason.trim() || !date || !actual.trim()) return
    setSaving(true)
    setError('')
    try {
      const updated = await reconcileAccountBalance(account.id, {
        actualBalancePaise: rupeesToPaise(Number(actual)),
        reason,
        occurredAt: new Date(`${date}T12:00:00`).toISOString()
      })
      setAccounts((current) => current.map((item) => String(item.id) === String(updated.id) ? updated : item))
      setEditingId(null)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Artha could not reconcile this balance.')
    } finally { setSaving(false) }
  }

  function replace(updated: ManagedAccount) {
    setAccounts((current) => current.some((item) => String(item.id) === String(updated.id)) ? current.map((item) => String(item.id) === String(updated.id) ? updated : item) : [...current, updated])
  }

  async function archive(account: ManagedAccount, archived: boolean) {
    setSaving(true); setError('')
    try { replace(await setManagedAccountArchived(account.id, archived)) } catch (caught) { setError(caught instanceof Error ? caught.message : 'Artha could not update this account.') } finally { setSaving(false) }
  }

  return (
    <section aria-labelledby="accounts-cards-heading" aria-label="Accounts & cards" className="mt-7 rounded-[24px] border border-line bg-white p-4 shadow-card dark:border-night-border dark:bg-night-surface sm:p-6">
      <p className="text-xs font-semibold uppercase tracking-[0.12em] text-moss-700">Money sources</p>
      <h2 id="accounts-cards-heading" className="font-display mt-1 text-xl font-bold">Accounts & cards</h2>
      <p className="mt-2 text-sm leading-6 text-[#66746d] tone-muted">Keep each displayed balance aligned with its latest statement. Reconciliation adds an audited correction; it never rewrites your opening balance or spending history.</p>
      <button type="button" onClick={() => setShowAdd((value) => !value)} className="mt-4 min-h-11 rounded-xl bg-moss-900 px-4 text-sm font-semibold text-white">{showAdd ? 'Cancel new account' : 'Add account or card'}</button>
      {showAdd && <AccountEditor onCancel={() => setShowAdd(false)} onSave={async (input) => { replace(await createManagedAccount(input)); setShowAdd(false) }} />}
      {error && <p role="alert" className="mt-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">{error}</p>}
      {loading ? <p role="status" className="mt-5 text-sm text-[#66746d] tone-muted">Loading accounts…</p> : accounts.filter((account) => !account.isArchived).length === 0 ? <p className="mt-5 text-sm text-[#66746d] tone-muted">No active accounts found.</p> : <div className="mt-5 space-y-3">{accounts.filter((account) => !account.isArchived).map((account) => {
        const isCard = account.kind === 'credit_card'
        const availableCredit = isCard && account.creditLimitPaise !== null ? account.creditLimitPaise + account.currentBalancePaise : null
        return <article key={String(account.id)} className="rounded-2xl border border-line p-4 dark:border-night-border">
          <div className="flex flex-wrap items-start justify-between gap-3"><div><h3 className="font-semibold">{account.name}</h3><p className="mt-1 text-xs capitalize text-[#718078] tone-muted">{account.kind.replace('_', ' ')}</p></div><div className="text-right"><p className="font-display text-xl font-bold tabular-nums">{formatMoney(account.currentBalancePaise)}</p><p className="mt-1 text-xs text-[#718078] tone-muted">{isCard ? 'Current card balance' : 'Available balance'}</p>{availableCredit !== null && <p className="mt-1 text-xs text-[#718078] tone-muted">Available credit {formatMoney(availableCredit)}</p>}</div></div>
          {String(manageId) === String(account.id) && <AccountEditor account={account} onCancel={() => setManageId(null)} onSave={async (input) => { replace(await updateManagedAccount(account.id, { name: input.name, creditLimitPaise: input.credit_limit_paise, statementDay: input.statement_day, paymentDueDay: input.payment_due_day })); setManageId(null) }} />}
          {String(editingId) === String(account.id) ? <form onSubmit={(event) => void submit(event, account)} className="mt-4 grid gap-3 rounded-2xl bg-moss-50 p-4 dark:bg-night-raised sm:grid-cols-2">
            <label className="text-xs font-semibold">Actual balance (₹)<input aria-label={`Actual balance for ${account.name}`} value={actual} onChange={(event) => setActual(event.target.value)} type="number" step="0.01" required className="mt-1 min-h-11 w-full rounded-xl border border-line bg-white px-3 text-sm dark:border-night-border dark:bg-night-surface" /></label>
            <label className="text-xs font-semibold">As of date<input aria-label={`Balance date for ${account.name}`} value={date} onChange={(event) => setDate(event.target.value)} type="date" required className="mt-1 min-h-11 w-full rounded-xl border border-line bg-white px-3 text-sm dark:border-night-border dark:bg-night-surface" /></label>
            <label className="text-xs font-semibold sm:col-span-2">Reason<input aria-label={`Reconciliation reason for ${account.name}`} value={reason} onChange={(event) => setReason(event.target.value)} maxLength={240} required className="mt-1 min-h-11 w-full rounded-xl border border-line bg-white px-3 text-sm dark:border-night-border dark:bg-night-surface" /></label>
            <div className="flex gap-2 sm:col-span-2"><button disabled={saving} className="min-h-11 rounded-xl bg-moss-900 px-4 text-sm font-semibold text-white disabled:opacity-60">{saving ? 'Saving…' : 'Review and reconcile'}</button><button type="button" onClick={() => setEditingId(null)} className="min-h-11 rounded-xl border border-line px-4 text-sm font-semibold">Cancel</button></div>
          </form> : <div className="mt-4 flex flex-wrap gap-2"><button type="button" onClick={() => begin(account)} aria-label={`Set actual balance for ${account.name}`} className="min-h-11 rounded-xl border border-line px-4 text-sm font-semibold text-moss-800">Set actual balance</button><button type="button" onClick={() => setManageId(account.id)} className="min-h-11 rounded-xl border border-line px-4 text-sm font-semibold">Edit details</button><button type="button" disabled={saving || account.currentBalancePaise !== 0} title={account.currentBalancePaise !== 0 ? 'Set the balance to zero before archiving.' : undefined} onClick={() => void archive(account, true)} className="min-h-11 rounded-xl border border-line px-4 text-sm font-semibold disabled:opacity-50">Archive</button></div>}
        </article>
      })}</div>}
      {!loading && accounts.some((account) => account.isArchived) && <details className="mt-5"><summary className="min-h-11 cursor-pointer py-3 text-sm font-semibold">Archived accounts</summary><div className="space-y-2">{accounts.filter((account) => account.isArchived).map((account) => <div key={String(account.id)} className="flex items-center justify-between gap-3 rounded-xl border border-line p-3"><span className="text-sm font-semibold">{account.name}</span><button type="button" disabled={saving} onClick={() => void archive(account, false)} className="min-h-11 rounded-xl border border-line px-4 text-sm font-semibold">Restore</button></div>)}</div></details>}
      {!loading && <button type="button" onClick={() => void load()} className="mt-4 min-h-11 rounded-xl px-3 text-sm font-semibold text-moss-800">Refresh accounts</button>}
    </section>
  )
}

function AccountEditor({ account, onSave, onCancel }: { account?: ManagedAccount; onSave: (input: import('../types').AccountSetupInput) => Promise<void>; onCancel: () => void }) {
  const [name, setName] = useState(account?.name ?? '')
  const [kind, setKind] = useState<import('../types').SetupAccountKind>(account?.kind === 'other' ? 'bank' : account?.kind ?? 'bank')
  const [balance, setBalance] = useState(account ? String(account.openingBalancePaise / 100) : '0')
  const [limit, setLimit] = useState(account?.creditLimitPaise === null || account?.creditLimitPaise === undefined ? '' : String(account.creditLimitPaise / 100))
  const [statement, setStatement] = useState(account?.statementDay?.toString() ?? '')
  const [due, setDue] = useState(account?.paymentDueDay?.toString() ?? '')
  const [busy, setBusy] = useState(false)
  const [formError, setFormError] = useState('')
  return <form onSubmit={(event) => { event.preventDefault(); setBusy(true); setFormError(''); void onSave({ name, kind, opening_balance_paise: account?.openingBalancePaise ?? (kind === 'credit_card' ? -Math.abs(rupeesToPaise(Number(balance))) : rupeesToPaise(Number(balance))), credit_limit_paise: kind === 'credit_card' && limit ? rupeesToPaise(Number(limit)) : null, statement_day: kind === 'credit_card' && statement ? Number(statement) : null, payment_due_day: kind === 'credit_card' && due ? Number(due) : null }).catch((caught) => setFormError(caught instanceof Error ? caught.message : 'Artha could not save this account.')).finally(() => setBusy(false)) }} className="mt-4 grid gap-3 rounded-2xl bg-moss-50 p-4 dark:bg-night-raised sm:grid-cols-2">
    {formError && <p role="alert" className="rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800 sm:col-span-2">{formError}</p>}
    <label className="text-xs font-semibold">Name<input value={name} onChange={(event) => setName(event.target.value)} required maxLength={80} className="mt-1 min-h-11 w-full rounded-xl border border-line bg-white px-3 dark:bg-night-surface" /></label>
    <label className="text-xs font-semibold">Type<select value={kind} disabled={Boolean(account)} onChange={(event) => setKind(event.target.value as import('../types').SetupAccountKind)} className="mt-1 min-h-11 w-full rounded-xl border border-line bg-white px-3 dark:bg-night-surface"><option value="bank">Bank</option><option value="cash">Cash</option><option value="wallet">Wallet</option><option value="credit_card">Credit card</option></select></label>
    {!account && <label className="text-xs font-semibold">{kind === 'credit_card' ? 'Current outstanding (₹)' : 'Starting balance (₹)'}<input value={balance} onChange={(event) => setBalance(event.target.value)} type="number" min="0" step="0.01" className="mt-1 min-h-11 w-full rounded-xl border border-line bg-white px-3 dark:bg-night-surface" /></label>}
    {kind === 'credit_card' && <><label className="text-xs font-semibold">Credit limit (₹)<input value={limit} onChange={(event) => setLimit(event.target.value)} type="number" min="0" step="0.01" className="mt-1 min-h-11 w-full rounded-xl border border-line bg-white px-3 dark:bg-night-surface" /></label><label className="text-xs font-semibold">Statement day<input value={statement} onChange={(event) => setStatement(event.target.value)} type="number" min="1" max="31" className="mt-1 min-h-11 w-full rounded-xl border border-line bg-white px-3 dark:bg-night-surface" /></label><label className="text-xs font-semibold">Payment due day<input value={due} onChange={(event) => setDue(event.target.value)} type="number" min="1" max="31" className="mt-1 min-h-11 w-full rounded-xl border border-line bg-white px-3 dark:bg-night-surface" /></label></>}
    <div className="flex gap-2 sm:col-span-2"><button disabled={busy} className="min-h-11 rounded-xl bg-moss-900 px-4 text-sm font-semibold text-white">{busy ? 'Saving…' : account ? 'Save details' : 'Add account'}</button><button type="button" onClick={onCancel} className="min-h-11 rounded-xl border border-line px-4 text-sm font-semibold">Cancel</button></div>
  </form>
}

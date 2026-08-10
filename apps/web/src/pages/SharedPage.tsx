import { ArrowDownRight, CheckCircle2, HandCoins, UsersRound, X } from 'lucide-react'
import { useRef, useState } from 'react'
import { Card, Badge, Button } from '../components/ui'
import { formatMoney, rupeesToPaise } from '../lib/money'
import { useModalSafety } from '../lib/useModalSafety'
import type { EntityId, LedgerAccount, MemberBalance, Transaction, UserProfile } from '../types'

type SettlementInput = { memberId: EntityId; accountId: EntityId; amountPaise: number; settledAt: string; note: string }

export function SharedPage({ transactions, sharedBalancePaise, memberBalances, demoMode, profile, accounts = [], onSettle }: { transactions: Transaction[]; sharedBalancePaise: number; memberBalances: MemberBalance[]; demoMode: boolean; profile: UserProfile; accounts?: LedgerAccount[]; onSettle?: (input: SettlementInput) => Promise<void> }) {
  const shared = transactions.filter((transaction) => transaction.memberSplits.length > 0)
  const [settlingWith, setSettlingWith] = useState<MemberBalance | null>(null)
  const displayedOwed = sharedBalancePaise
  const balanceLabel = displayedOwed > 0
    ? 'Family owes you'
    : displayedOwed < 0
      ? 'You owe family'
      : memberBalances.length === 0
        ? 'Everyone is settled up'
        : 'Individual balances still need settling'

  return (
    <div className="mx-auto max-w-3xl">
      <div className="flex items-end justify-between">
        <div><p className="text-sm font-medium text-[#738078] tone-muted">Your shared money</p><h1 className="font-display mt-1 text-3xl font-bold tracking-[-0.05em]">{profile.householdName}</h1></div>
        {demoMode && <Badge tone="green">Demo data</Badge>}
      </div>

      <Card className="relative mt-6 overflow-hidden border-0 bg-moss-900 p-6 text-white dark:bg-night-raised sm:p-8">
        <div className="absolute -right-10 -top-14 h-44 w-44 rounded-full border-[28px] border-white/[0.04]" />
        <div className="relative">
          <div className="flex items-center gap-2 text-sm text-moss-200"><UsersRound className="h-4 w-4" aria-hidden="true" /> Current shared balance</div>
          <p className="font-display mt-4 text-4xl font-bold tracking-[-0.05em] sm:text-5xl">{formatMoney(displayedOwed)}</p>
          <p className="mt-2 text-sm text-moss-200">{balanceLabel}</p>
          <div className="mt-7 flex items-center gap-2 text-xs text-moss-200"><CheckCircle2 className="h-4 w-4" aria-hidden="true" /> Calculated from your complete ledger</div>
        </div>
      </Card>

      {memberBalances.length > 0 && <div className="mt-4 grid gap-3 sm:grid-cols-2">{memberBalances.map((balance) => <Card key={balance.id} className="flex items-center justify-between gap-3 p-4"><div className="min-w-0"><p className="truncate text-sm font-semibold">{balance.name}</p><p className="mt-1 text-xs text-[#748079] tone-muted">{balance.status || (balance.balancePaise >= 0 ? 'owes you' : 'you owe')}</p><button type="button" onClick={() => setSettlingWith(balance)} className="mt-2 min-h-11 rounded-xl text-xs font-bold text-moss-700 underline-offset-4 hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-moss-400" aria-label={`Record repayment with ${balance.name}`}><HandCoins className="mr-1.5 inline h-4 w-4" aria-hidden="true" />Record repayment</button></div><p className="shrink-0 font-display text-lg font-bold text-moss-800">{formatMoney(Math.abs(balance.balancePaise))}</p></Card>)}</div>}

      <div className="mt-6 grid grid-cols-2 gap-3">
        <Card className="p-4 sm:p-5"><p className="text-xs text-[#748079] tone-muted">Paid in loaded activity</p><p className="font-display mt-1.5 text-xl font-bold">{formatMoney(shared.reduce((sum, item) => sum + item.amountPaise, 0))}</p></Card>
        <Card className="p-4 sm:p-5"><p className="text-xs text-[#748079] tone-muted">Your share in loaded activity</p><p className="font-display mt-1.5 text-xl font-bold">{formatMoney(shared.reduce((sum, item) => sum + item.personalSharePaise, 0))}</p></Card>
      </div>

      <div className="mt-7 flex items-center justify-between"><h2 className="font-display text-xl font-bold tracking-[-0.03em]">Recent shared expenses</h2><span className="text-xs text-[#7a867f] tone-muted">Loaded history</span></div>
      <Card className="mt-3 overflow-hidden">
        {shared.length ? <div className="divide-y divide-line">{shared.map((transaction) => (
          <article key={transaction.id} className="flex items-center gap-3 p-5 sm:px-6">
            <div className="grid h-11 w-11 shrink-0 place-items-center rounded-2xl bg-moss-100 text-moss-800"><ArrowDownRight className="h-5 w-5" aria-hidden="true" /></div>
            <div className="min-w-0 flex-1"><div className="flex justify-between gap-3"><p className="truncate text-sm font-semibold">{transaction.merchant}</p><p className="shrink-0 text-sm font-bold text-moss-800">{formatMoney(transaction.memberSplits.reduce((sum, split) => sum + split.amountPaise, 0))}</p></div><div className="mt-1 flex justify-between gap-2 text-xs text-[#7b8781] tone-muted"><span className="truncate">With {transaction.memberSplits.map((split) => split.memberName).join(', ')}</span><span className="shrink-0">{new Intl.DateTimeFormat('en-IN', { day: 'numeric', month: 'short' }).format(new Date(`${transaction.occurredAt}T12:00:00`))}</span></div></div>
          </article>
        ))}</div> : <div className="py-14 text-center"><UsersRound className="mx-auto h-7 w-7 text-[#9aa49f] tone-subtle" aria-hidden="true" /><p className="mt-3 font-semibold">Nothing shared yet</p><p className="mt-1 text-sm text-[#7b8781] tone-muted">Shared expenses will appear here.</p></div>}
      </Card>

      <div className="mt-4 rounded-2xl border border-line bg-white/50 p-4 text-xs leading-5 text-[#6e7a74] tone-muted dark:bg-night-surface/80">
        <strong className="text-ink">How this works:</strong> Artha tracks the full amount leaving your account separately from the amount that is actually your spending. A settlement clears this balance without counting as new income.
      </div>
      {settlingWith && onSettle && <SettlementDialog balance={settlingWith} accounts={accounts} onClose={() => setSettlingWith(null)} onSettle={async (input) => { await onSettle(input); setSettlingWith(null) }} />}
    </div>
  )
}

function SettlementDialog({ balance, accounts, onClose, onSettle }: { balance: MemberBalance; accounts: LedgerAccount[]; onClose: () => void; onSettle: (input: SettlementInput) => Promise<void> }) {
  const dialogRef = useRef<HTMLElement>(null)
  useModalSafety(dialogRef, onClose)
  const [amount, setAmount] = useState(String(Math.abs(balance.balancePaise) / 100))
  const [accountId, setAccountId] = useState(accounts[0]?.id === undefined ? '' : String(accounts[0].id))
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10))
  const [note, setNote] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const amountPaise = rupeesToPaise(Number(amount))
  const valid = amountPaise > 0 && amountPaise <= Math.abs(balance.balancePaise) && Boolean(accountId) && Boolean(date)

  async function submit() {
    if (!valid || saving) return
    setSaving(true)
    setError('')
    try {
      await onSettle({ memberId: balance.id, accountId, amountPaise, settledAt: new Date(`${date}T12:00:00`).toISOString(), note: note.trim() })
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'The repayment was not recorded. Please try again.')
    } finally {
      setSaving(false)
    }
  }

  return <div className="fixed inset-0 z-50 grid items-end bg-black/35 sm:place-items-center sm:p-6" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose() }}><section ref={dialogRef} role="dialog" aria-modal="true" aria-label="Record repayment" className="max-h-[92svh] w-full overflow-y-auto rounded-t-[28px] border border-line bg-white p-5 shadow-2xl dark:border-night-border dark:bg-night-surface sm:max-w-lg sm:rounded-[28px] sm:p-6"><div className="flex items-start justify-between gap-4"><div><p className="text-xs font-bold uppercase tracking-[0.12em] text-moss-700">Shared balance</p><h2 className="font-display mt-1 text-2xl font-bold tracking-[-0.04em]">Record repayment with {balance.name}</h2></div><button type="button" onClick={onClose} className="grid h-11 w-11 shrink-0 place-items-center rounded-xl hover:bg-moss-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-moss-400" aria-label="Close repayment form"><X className="h-5 w-5" aria-hidden="true" /></button></div><p className="mt-4 rounded-2xl bg-moss-50 p-3 text-sm leading-6 text-moss-900 dark:bg-night-raised dark:text-night-ink">Use this only when money actually moved. Artha updates the shared balance without counting it as income or spending.</p><div className="mt-5 grid gap-4"><label className="grid gap-1.5 text-sm font-semibold">Amount in rupees<input aria-label="Amount in rupees" type="number" inputMode="decimal" min="0.01" max={Math.abs(balance.balancePaise) / 100} step="0.01" value={amount} onChange={(event) => setAmount(event.target.value)} className="min-h-12 rounded-xl border border-line bg-white px-3 outline-none focus-visible:ring-4 focus-visible:ring-moss-100 dark:bg-night-input" /></label><label className="grid gap-1.5 text-sm font-semibold">Account where money moved<select aria-label="Account where money moved" value={accountId} onChange={(event) => setAccountId(event.target.value)} className="min-h-12 rounded-xl border border-line bg-white px-3 outline-none focus-visible:ring-4 focus-visible:ring-moss-100 dark:bg-night-input"><option value="">Choose an account</option>{accounts.map((account) => <option key={String(account.id)} value={String(account.id)}>{account.name}</option>)}</select></label><label className="grid gap-1.5 text-sm font-semibold">Repayment date<input aria-label="Repayment date" type="date" value={date} onChange={(event) => setDate(event.target.value)} className="min-h-12 rounded-xl border border-line bg-white px-3 outline-none focus-visible:ring-4 focus-visible:ring-moss-100 dark:bg-night-input" /></label><label className="grid gap-1.5 text-sm font-semibold">Note (optional)<input aria-label="Note (optional)" value={note} onChange={(event) => setNote(event.target.value)} className="min-h-12 rounded-xl border border-line bg-white px-3 outline-none focus-visible:ring-4 focus-visible:ring-moss-100 dark:bg-night-input" /></label>{amountPaise > Math.abs(balance.balancePaise) && <p role="alert" className="text-sm text-red-700">The repayment cannot be more than {formatMoney(Math.abs(balance.balancePaise))}.</p>}{error && <p role="alert" className="rounded-xl bg-red-50 p-3 text-sm text-red-800">{error}</p>}<div className="grid gap-3 sm:grid-cols-2"><Button variant="secondary" onClick={onClose}>Cancel</Button><Button loading={saving} disabled={!valid} onClick={() => void submit()}>Confirm repayment</Button></div></div></section></div>
}

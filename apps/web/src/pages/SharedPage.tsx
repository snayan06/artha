import { ArrowDownRight, CheckCircle2, UsersRound } from 'lucide-react'
import { Card, Badge } from '../components/ui'
import { formatMoney } from '../lib/money'
import type { MemberBalance, Transaction, UserProfile } from '../types'

export function SharedPage({ transactions, sharedBalancePaise, memberBalances, demoMode, profile }: { transactions: Transaction[]; sharedBalancePaise: number; memberBalances: MemberBalance[]; demoMode: boolean; profile: UserProfile }) {
  const shared = transactions.filter((transaction) => transaction.memberSplits.length > 0)
  const displayedOwed = sharedBalancePaise
  const balanceLabel = displayedOwed > 0 ? 'Family owes you' : displayedOwed < 0 ? 'You owe family' : 'Everyone is settled up'

  return (
    <div className="mx-auto max-w-3xl">
      <div className="flex items-end justify-between">
        <div><p className="text-sm font-medium text-[#738078] tone-muted">Your shared money</p><h1 className="font-display mt-1 text-3xl font-bold tracking-[-0.05em]">{profile.householdName}</h1></div>
        {demoMode && <Badge tone="green">Demo data</Badge>}
      </div>

      <Card className="relative mt-6 overflow-hidden border-0 bg-moss-900 p-6 text-white dark:bg-night-raised sm:p-8">
        <div className="absolute -right-10 -top-14 h-44 w-44 rounded-full border-[28px] border-white/[0.04]" />
        <div className="relative">
          <div className="flex items-center gap-2 text-sm text-moss-200"><UsersRound className="h-4 w-4" /> Current shared balance</div>
          <p className="font-display mt-4 text-4xl font-bold tracking-[-0.05em] sm:text-5xl">{formatMoney(displayedOwed)}</p>
          <p className="mt-2 text-sm text-moss-200">{balanceLabel}</p>
          <div className="mt-7 flex items-center gap-2 text-xs text-moss-200"><CheckCircle2 className="h-4 w-4" /> Based on {shared.length} confirmed shared expenses</div>
        </div>
      </Card>

      {memberBalances.length > 0 && <div className="mt-4 grid gap-3 sm:grid-cols-2">{memberBalances.map((balance) => <Card key={balance.id} className="flex items-center justify-between gap-3 p-4"><div className="min-w-0"><p className="truncate text-sm font-semibold">{balance.name}</p><p className="mt-1 text-xs text-[#748079] tone-muted">{balance.status || (balance.balancePaise >= 0 ? 'owes you' : 'you owe')}</p></div><p className="shrink-0 font-display text-lg font-bold text-moss-800">{formatMoney(balance.balancePaise)}</p></Card>)}</div>}

      <div className="mt-6 grid grid-cols-2 gap-3">
        <Card className="p-4 sm:p-5"><p className="text-xs text-[#748079] tone-muted">{profile.displayName} paid</p><p className="font-display mt-1.5 text-xl font-bold">{formatMoney(shared.reduce((sum, item) => sum + item.amountPaise, 0))}</p></Card>
        <Card className="p-4 sm:p-5"><p className="text-xs text-[#748079] tone-muted">Your actual share</p><p className="font-display mt-1.5 text-xl font-bold">{formatMoney(shared.reduce((sum, item) => sum + item.personalSharePaise, 0))}</p></Card>
      </div>

      <div className="mt-7 flex items-center justify-between"><h2 className="font-display text-xl font-bold tracking-[-0.03em]">What makes up this balance</h2><span className="text-xs text-[#7a867f] tone-muted">All time</span></div>
      <Card className="mt-3 overflow-hidden">
        {shared.length ? <div className="divide-y divide-line">{shared.map((transaction) => (
          <article key={transaction.id} className="flex items-center gap-3 p-5 sm:px-6">
            <div className="grid h-11 w-11 shrink-0 place-items-center rounded-2xl bg-moss-100 text-moss-800"><ArrowDownRight className="h-5 w-5" /></div>
            <div className="min-w-0 flex-1"><div className="flex justify-between gap-3"><p className="truncate text-sm font-semibold">{transaction.merchant}</p><p className="shrink-0 text-sm font-bold text-moss-800">{formatMoney(transaction.memberSplits.reduce((sum, split) => sum + split.amountPaise, 0))}</p></div><div className="mt-1 flex justify-between gap-2 text-xs text-[#7b8781] tone-muted"><span className="truncate">With {transaction.memberSplits.map((split) => split.memberName).join(', ')}</span><span className="shrink-0">{new Intl.DateTimeFormat('en-IN', { day: 'numeric', month: 'short' }).format(new Date(`${transaction.occurredAt}T12:00:00`))}</span></div></div>
          </article>
        ))}</div> : <div className="py-14 text-center"><UsersRound className="mx-auto h-7 w-7 text-[#9aa49f] tone-subtle" /><p className="mt-3 font-semibold">Nothing shared yet</p><p className="mt-1 text-sm text-[#7b8781] tone-muted">Shared expenses will appear here.</p></div>}
      </Card>

      <div className="mt-4 rounded-2xl border border-line bg-white/50 p-4 text-xs leading-5 text-[#6e7a74] tone-muted dark:bg-night-surface/80">
        <strong className="text-ink">How this works:</strong> Hisab tracks the full amount leaving your account separately from the amount that is actually your spending. A settlement clears this balance without counting as new income.
      </div>
    </div>
  )
}

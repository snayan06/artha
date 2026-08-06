import { ArrowRight, Eye, EyeOff, Sparkles, UsersRound, WalletCards } from 'lucide-react'
import { useState } from 'react'
import type { Dashboard, UserProfile } from '../types'
import { formatMoney } from '../lib/money'
import { AppLink, useRouter } from '../lib/router'
import { Card, Badge, Button } from '../components/ui'
import { SpendChart } from '../components/SpendChart'
import { TransactionRow } from '../components/TransactionRow'

export function HomePage({ dashboard, demoMode, profile }: { dashboard: Dashboard; demoMode: boolean; profile: UserProfile }) {
  const [showBalance, setShowBalance] = useState(true)
  const [capture, setCapture] = useState('')
  const { navigate } = useRouter()
  const sharedLabel = dashboard.sharedBalancePaise > 0 ? 'Family owes you' : dashboard.sharedBalancePaise < 0 ? 'You owe family' : 'You are settled up'
  const hour = new Date().getHours()
  const greeting = hour < 12 ? 'Good morning' : hour < 17 ? 'Good afternoon' : 'Good evening'

  function startCapture(event: React.FormEvent) {
    event.preventDefault()
    if (capture.trim()) navigate('/add', { capture: capture.trim() })
  }

  return (
    <div className="space-y-5 sm:space-y-7">
      <div className="flex items-end justify-between">
        <div>
          <p className="break-words text-sm font-medium text-[#728078] tone-muted">{greeting}, {profile.displayName}</p>
          <h1 className="font-display mt-1 text-balance text-2xl font-bold tracking-[-0.04em] sm:text-3xl">Your money, made clear.</h1>
        </div>
        {demoMode && <Badge tone="green">Demo data</Badge>}
      </div>

      <div className="grid gap-5 lg:grid-cols-[1.2fr_.8fr]">
        <Card className="overflow-hidden border-0 bg-moss-900 p-5 text-white dark:bg-night-raised sm:p-7">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-sm text-moss-200"><WalletCards className="h-4 w-4" aria-hidden="true" /> Available across accounts</div>
            <button onClick={() => setShowBalance((value) => !value)} className="grid h-11 w-11 place-items-center rounded-full bg-white/10 text-moss-100 transition hover:bg-white/20 focus:outline-none focus-visible:ring-2 focus-visible:ring-white" aria-label={showBalance ? 'Hide Balance' : 'Show Balance'}>
              {showBalance ? <Eye className="h-4 w-4" aria-hidden="true" /> : <EyeOff className="h-4 w-4" aria-hidden="true" />}
            </button>
          </div>
          <p className="font-display mt-5 text-[38px] font-semibold leading-none tracking-[-0.05em] tabular-nums sm:text-5xl">
            {showBalance ? formatMoney(dashboard.availablePaise) : '₹••••••'}
          </p>
          <div className="mt-7 grid grid-cols-2 gap-3">
            <div className="rounded-2xl bg-white/[0.07] p-3.5">
              <p className="text-xs text-moss-200">Income tracked</p>
              <p className="mt-1.5 text-lg font-semibold tabular-nums">{formatMoney(dashboard.incomePaise)}</p>
            </div>
            <div className="rounded-2xl bg-white/[0.07] p-3.5">
              <p className="text-xs text-moss-200">Spending tracked</p>
              <p className="mt-1.5 text-lg font-semibold tabular-nums">{formatMoney(dashboard.spendPaise)}</p>
            </div>
          </div>
        </Card>

        <Card className="flex flex-col justify-between p-5 sm:p-6">
          <div className="flex items-start justify-between">
            <div>
              <p className="text-sm font-semibold text-[#5f6c66] tone-muted">{profile.householdName}</p>
              <p className="font-display mt-2 text-3xl font-bold tracking-[-0.04em] text-moss-900 tabular-nums">{formatMoney(dashboard.sharedBalancePaise)}</p>
              <p className="mt-1 text-xs text-[#7c8781] tone-muted">{sharedLabel}</p>
            </div>
            <div className="grid h-11 w-11 place-items-center rounded-2xl bg-moss-100 text-moss-800"><UsersRound className="h-5 w-5" aria-hidden="true" /></div>
          </div>
          <AppLink to="/shared" className="mt-6 flex items-center justify-between rounded-2xl bg-moss-50 px-4 py-3 text-sm font-semibold text-moss-800 transition hover:bg-moss-100">
            Review shared expenses <ArrowRight className="h-4 w-4" aria-hidden="true" />
          </AppLink>
        </Card>
      </div>

      <Card className="p-4 sm:p-5">
        <form onSubmit={startCapture}>
          <div className="mb-3 flex items-center gap-2 text-sm font-semibold"><Sparkles className="h-4 w-4 text-moss-600" aria-hidden="true" /> What happened?</div>
          <div className="flex flex-col gap-3 sm:flex-row">
            <label className="sr-only" htmlFor="home-capture">Describe a transaction</label>
            <input id="home-capture" name="transaction-capture" autoComplete="off" value={capture} onChange={(event) => setCapture(event.target.value)} placeholder={`${profile.members[0] ? `Paid 850 for dinner with ${profile.members[0].name}` : 'Paid 850 for dinner yesterday'}…`} className="min-h-12 min-w-0 flex-1 rounded-2xl border border-line bg-[#fafbf9] px-4 text-[15px] outline-none transition placeholder:text-[#9ca69f] tone-subtle focus-visible:border-moss-400 focus-visible:ring-4 focus-visible:ring-moss-100 dark:bg-night-input" />
            <Button type="submit" disabled={!capture.trim()} className="sm:px-6">Make draft <ArrowRight className="h-4 w-4" aria-hidden="true" /></Button>
          </div>
          <p className="mt-2.5 text-[11px] text-[#8b958f] tone-subtle">Nothing is saved until you review and confirm.</p>
        </form>
      </Card>

      <div className="grid gap-5 lg:grid-cols-[.92fr_1.08fr]">
        <Card className="min-w-0 p-5 sm:p-6">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="font-display text-lg font-bold tracking-[-0.02em]">Six-month rhythm</h2>
              <div className="mt-1.5 flex gap-3 text-[11px] text-[#78847e] tone-muted"><span>● <span className="ml-1">Income</span></span><span className="text-moss-800">● <span className="ml-1 text-[#78847e] tone-muted">Spend</span></span></div>
            </div>
          </div>
          <div className="mt-3"><SpendChart data={dashboard.monthly} /></div>
        </Card>

        <Card className="min-w-0 p-5 sm:p-6">
          <div className="mb-1 flex items-center justify-between">
            <h2 className="font-display text-lg font-bold tracking-[-0.02em]">Recent activity</h2>
            <AppLink to="/transactions" className="inline-flex min-h-11 items-center text-xs font-semibold text-moss-700 hover:text-moss-900">View all</AppLink>
          </div>
          <div className="divide-y divide-line">
            {dashboard.recentTransactions.map((transaction) => <TransactionRow key={transaction.id} transaction={transaction} compact />)}
          </div>
        </Card>
      </div>
    </div>
  )
}

import { Search, SlidersHorizontal, X } from 'lucide-react'
import { useMemo, useState } from 'react'
import { TransactionRow } from '../components/TransactionRow'
import { Card, Badge } from '../components/ui'
import { formatMoney } from '../lib/money'
import type { Transaction } from '../types'

type Filter = 'all' | 'spend' | 'income' | 'shared'

export function TransactionsPage({ transactions, demoMode }: { transactions: Transaction[]; demoMode: boolean }) {
  const [search, setSearch] = useState('')
  const [filter, setFilter] = useState<Filter>('all')
  const filtered = useMemo(() => transactions.filter((transaction) => {
    const haystack = `${transaction.merchant} ${transaction.category} ${transaction.account}`.toLowerCase()
    const matchesSearch = haystack.includes(search.toLowerCase())
    const matchesFilter = filter === 'all' || (filter === 'income' && transaction.kind === 'credit') || (filter === 'spend' && transaction.kind === 'debit') || (filter === 'shared' && transaction.memberSplits.length > 0)
    return matchesSearch && matchesFilter
  }), [filter, search, transactions])
  const netPaise = filtered.reduce((total, transaction) => total + (transaction.kind === 'credit' ? transaction.amountPaise : -transaction.amountPaise), 0)

  return (
    <div className="mx-auto max-w-3xl">
      <div className="flex items-end justify-between">
        <div><p className="text-sm font-medium text-[#738078] tone-muted">Your complete ledger</p><h1 className="font-display mt-1 text-3xl font-bold tracking-[-0.05em]">Transactions</h1></div>
        {demoMode && <Badge tone="green">Demo data</Badge>}
      </div>
      <Card className="mt-6 p-4">
        <div className="relative">
          <Search className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-[#8a958f] tone-subtle" />
          <label className="sr-only" htmlFor="transaction-search">Search transactions</label>
          <input id="transaction-search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search merchant, category or account" className="min-h-12 w-full rounded-2xl border border-line bg-[#fafbf9] pl-11 pr-10 text-sm outline-none focus:border-moss-400 focus:ring-4 focus:ring-moss-100 dark:bg-night-input" />
          {search && <button onClick={() => setSearch('')} className="absolute right-3 top-1/2 grid h-7 w-7 -translate-y-1/2 place-items-center text-[#79857f] tone-muted" aria-label="Clear search"><X className="h-4 w-4" /></button>}
        </div>
        <div className="mt-3 flex items-center gap-2 overflow-x-auto scrollbar-none">
          <SlidersHorizontal className="mr-1 h-4 w-4 shrink-0 text-[#77837d] tone-muted" />
          {(['all', 'spend', 'income', 'shared'] as Filter[]).map((item) => <button key={item} onClick={() => setFilter(item)} className={`shrink-0 rounded-full px-3.5 py-2 text-xs font-semibold capitalize transition ${filter === item ? 'bg-moss-900 text-white dark:bg-[#27604e]' : 'bg-[#f1f3ef] text-[#68746e] tone-muted hover:bg-moss-100 dark:bg-night-raised'}`}>{item}</button>)}
        </div>
      </Card>

      <div className="mt-5 flex items-center justify-between px-1 text-xs text-[#748079] tone-muted"><span>{filtered.length} {filtered.length === 1 ? 'transaction' : 'transactions'}</span><span>Net <strong className={netPaise >= 0 ? 'text-moss-700' : 'text-ink'}>{formatMoney(netPaise, { sign: true })}</strong></span></div>
      <Card className="mt-3 px-5 sm:px-6">
        {filtered.length ? <div className="divide-y divide-line">{filtered.map((transaction) => <TransactionRow key={transaction.id} transaction={transaction} />)}</div> : <div className="py-16 text-center"><Search className="mx-auto h-7 w-7 text-[#9aa49f] tone-subtle" /><p className="mt-3 font-semibold">No matching transactions</p><p className="mt-1 text-sm text-[#7b8781] tone-muted">Try another search or filter.</p></div>}
      </Card>
    </div>
  )
}

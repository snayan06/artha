import { Search, SlidersHorizontal, X } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { TransactionRow } from '../components/TransactionRow'
import { TransactionDetailPanel } from '../components/TransactionDetailPanel'
import { Card, Badge } from '../components/ui'
import { formatMoney } from '../lib/money'
import type { CaptureCategory, LedgerAccount, Transaction, TransactionDraft } from '../types'

type Filter = 'all' | 'spend' | 'income' | 'transfers' | 'shared'
const noAccounts: LedgerAccount[] = []
const noCategories: CaptureCategory[] = []

export function TransactionsPage({
  transactions,
  demoMode,
  selectedTransactionId,
  accounts = noAccounts,
  categories = noCategories,
  onSearch,
  onFetchById,
  hasMore = false,
  onLoadMore,
  onUpdate,
  onVoid
}: {
  transactions: Transaction[]
  demoMode: boolean
  selectedTransactionId?: string
  accounts?: LedgerAccount[]
  categories?: CaptureCategory[]
  onSearch?: (query: string) => Promise<Transaction[]>
  onFetchById?: (id: string) => Promise<Transaction>
  hasMore?: boolean
  onLoadMore?: () => Promise<void>
  onUpdate?: (id: string, draft: TransactionDraft, reason: string) => Promise<void>
  onVoid?: (id: string, reason: string) => Promise<void>
}) {
  const [search, setSearch] = useState('')
  const [filter, setFilter] = useState<Filter>('all')
  const [account, setAccount] = useState('all')
  const [selectedId, setSelectedId] = useState(selectedTransactionId)
  const [searchResults, setSearchResults] = useState<Transaction[] | null>(null)
  const [searching, setSearching] = useState(false)
  const [searchIssue, setSearchIssue] = useState('')
  const [loadingMore, setLoadingMore] = useState(false)
  const [fetchedTransaction, setFetchedTransaction] = useState<Transaction | null>(null)
  const [loadingSelected, setLoadingSelected] = useState(false)
  const [selectedIssue, setSelectedIssue] = useState('')
  const [selectedAttempt, setSelectedAttempt] = useState(0)
  useEffect(() => {
    const query = search.trim()
    if (!query || !onSearch) {
      setSearchResults(null)
      setSearching(false)
      setSearchIssue('')
      return
    }
    let current = true
    const timeout = window.setTimeout(() => {
      setSearching(true)
      setSearchIssue('')
      void onSearch(query)
        .then((results) => {
          if (current) setSearchResults(results)
        })
        .catch(() => {
          if (current) setSearchIssue('Search is temporarily unavailable. Your ledger was not changed.')
        })
        .finally(() => {
          if (current) setSearching(false)
        })
    }, 250)
    return () => {
      current = false
      window.clearTimeout(timeout)
    }
  }, [onSearch, search])
  const visibleTransactions = searchResults ?? transactions
  const selectedTransaction = visibleTransactions.find((transaction) => transaction.id === selectedId)
    ?? transactions.find((transaction) => transaction.id === selectedId)
    ?? (fetchedTransaction?.id === selectedId ? fetchedTransaction : undefined)

  useEffect(() => {
    setSelectedId(selectedTransactionId)
    setFetchedTransaction(null)
    setSelectedIssue('')
  }, [selectedTransactionId])

  useEffect(() => {
    if (!selectedId || selectedTransaction || !onFetchById) {
      setLoadingSelected(false)
      return
    }
    let current = true
    setLoadingSelected(true)
    setSelectedIssue('')
    void onFetchById(selectedId)
      .then((transaction) => {
        if (current) setFetchedTransaction(transaction)
      })
      .catch(() => {
        if (current) setSelectedIssue('Could not load this ledger entry. Check the connection and try again.')
      })
      .finally(() => {
        if (current) setLoadingSelected(false)
      })
    return () => { current = false }
  }, [onFetchById, selectedAttempt, selectedId, selectedTransaction])
  const accountOptions = useMemo(() => [...new Set(visibleTransactions.flatMap((transaction) => [transaction.account, transaction.destinationAccount].filter((name): name is string => Boolean(name))))].sort((left, right) => left.localeCompare(right)), [visibleTransactions])
  const filtered = useMemo(() => visibleTransactions.filter((transaction) => {
    const haystack = `${transaction.merchant} ${transaction.category} ${transaction.account} ${transaction.destinationAccount ?? ''} ${transaction.note ?? ''}`.toLowerCase()
    const matchesSearch = haystack.includes(search.toLowerCase())
    const matchesFilter = filter === 'all' || (filter === 'income' && transaction.kind === 'credit') || (filter === 'spend' && transaction.kind === 'debit') || (filter === 'transfers' && transaction.kind === 'transfer') || (filter === 'shared' && (transaction.kind === 'settlement' || transaction.memberSplits.length > 0))
    const matchesAccount = account === 'all' || transaction.account === account || transaction.destinationAccount === account
    return matchesSearch && matchesFilter && matchesAccount
  }), [account, filter, search, visibleTransactions])
  const netPaise = filtered.reduce((total, transaction) => total + (transaction.kind === 'transfer' || transaction.kind === 'settlement' || transaction.kind === 'adjustment' ? 0 : transaction.kind === 'credit' ? transaction.amountPaise : -transaction.amountPaise), 0)

  return (
    <div className="mx-auto max-w-3xl">
      <div className="flex items-end justify-between">
        <div><p className="text-sm font-medium text-[#738078] tone-muted">Your complete ledger</p><h1 className="font-display mt-1 text-3xl font-bold tracking-[-0.05em]">Transactions</h1></div>
        {demoMode && <Badge tone="green">Demo data</Badge>}
      </div>
      <Card className="mt-6 p-4">
        <div className="relative">
          <Search className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-[#8a958f] tone-subtle" aria-hidden="true" />
          <label className="sr-only" htmlFor="transaction-search">Search transactions</label>
          <input id="transaction-search" name="transaction-search" type="search" autoComplete="off" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search merchant, category, account, or note…" className="min-h-12 w-full rounded-2xl border border-line bg-[#fafbf9] pl-11 pr-10 text-sm outline-none focus-visible:border-moss-400 focus-visible:ring-4 focus-visible:ring-moss-100 dark:bg-night-input" />
          {search && <button onClick={() => setSearch('')} className="absolute right-2 top-1/2 grid h-11 w-11 -translate-y-1/2 place-items-center rounded-xl text-[#79857f] tone-muted transition hover:bg-moss-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-moss-400" aria-label="Clear Search"><X className="h-4 w-4" aria-hidden="true" /></button>}
        </div>
        <p className="mt-2 min-h-5 text-xs text-[#748079] tone-muted" role="status" aria-live="polite">{searching ? 'Searching your complete ledger…' : searchIssue}</p>
        <div className="mt-3 grid gap-3 sm:grid-cols-[1fr_auto] sm:items-center">
          <div className="flex items-center gap-2 overflow-x-auto scrollbar-none">
            <SlidersHorizontal className="mr-1 h-4 w-4 shrink-0 text-[#77837d] tone-muted" aria-hidden="true" />
            {(['all', 'spend', 'income', 'transfers', 'shared'] as Filter[]).map((item) => <button key={item} onClick={() => setFilter(item)} aria-pressed={filter === item} className={`min-h-11 shrink-0 rounded-full px-3.5 py-2 text-xs font-semibold capitalize transition focus:outline-none focus-visible:ring-2 focus-visible:ring-moss-400 ${filter === item ? 'bg-moss-900 text-white dark:bg-[#27604e]' : 'bg-[#f1f3ef] text-[#68746e] tone-muted hover:bg-moss-100 dark:bg-night-raised'}`}>{item}</button>)}
          </div>
          <label className="grid gap-1 text-[11px] font-semibold uppercase tracking-[0.08em] text-[#748079] tone-muted">
            Account
            <select name="account-filter" aria-label="Filter by account" autoComplete="off" value={account} onChange={(event) => setAccount(event.target.value)} className="min-h-11 rounded-xl border border-line bg-white px-3 text-sm font-semibold normal-case tracking-normal text-ink outline-none focus-visible:border-moss-400 focus-visible:ring-4 focus-visible:ring-moss-100 dark:bg-night-input">
              <option value="all">All accounts</option>
              {accountOptions.map((name) => <option key={name} value={name}>{name}</option>)}
            </select>
          </label>
        </div>
      </Card>

      <div className="mt-5 flex items-center justify-between px-1 text-xs text-[#748079] tone-muted"><span>{filtered.length} {filtered.length === 1 ? 'transaction' : 'transactions'}{searchResults && filtered.length === 200 ? ' (first 200 matches)' : ''}</span><span className="tabular-nums">Net <strong className={netPaise >= 0 ? 'text-moss-700' : 'text-ink'}>{formatMoney(netPaise, { sign: true })}</strong></span></div>
      {loadingSelected && <p role="status" className="mt-3 rounded-2xl border border-line bg-white px-4 py-3 text-sm text-[#66746d] tone-muted dark:bg-night-surface">Loading the supporting ledger entry…</p>}
      {selectedIssue && <div role="alert" className="mt-3 flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-200"><span>{selectedIssue}</span><button type="button" onClick={() => setSelectedAttempt((current) => current + 1)} className="min-h-11 rounded-xl border border-amber-300 bg-white px-3 text-xs font-semibold text-amber-900 focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-500 dark:border-amber-800 dark:bg-night-raised dark:text-amber-200">Try loading entry again</button></div>}
      <Card className="mt-3 px-5 sm:px-6">
        {filtered.length ? <div className="divide-y divide-line">{filtered.map((transaction) => <TransactionRow key={transaction.id} transaction={transaction} onSelect={() => setSelectedId(transaction.id)} />)}</div> : <div className="py-16 text-center"><Search className="mx-auto h-7 w-7 text-[#9aa49f] tone-subtle" aria-hidden="true" /><p className="mt-3 font-semibold">No matching transactions</p><p className="mt-1 text-sm text-[#7b8781] tone-muted">Try another search or filter.</p></div>}
      </Card>
      {!search.trim() && hasMore && onLoadMore && <div className="mt-4 flex justify-center"><button type="button" disabled={loadingMore} onClick={() => { setLoadingMore(true); void onLoadMore().finally(() => setLoadingMore(false)) }} className="min-h-11 rounded-xl border border-line bg-white px-5 text-sm font-semibold transition hover:border-moss-300 hover:bg-moss-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-moss-400 disabled:cursor-wait disabled:opacity-60 dark:bg-night-surface dark:hover:bg-night-raised">{loadingMore ? 'Loading older activity…' : 'Load older activity'}</button></div>}
      {selectedTransaction && (
        <TransactionDetailPanel
          transaction={selectedTransaction}
          accounts={accounts}
          categories={categories}
          onClose={() => { setSelectedId(undefined); setFetchedTransaction(null); setSelectedIssue('') }}
          onUpdate={onUpdate}
          onVoid={onVoid}
        />
      )}
    </div>
  )
}

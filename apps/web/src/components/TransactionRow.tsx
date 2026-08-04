import { ArrowDownLeft, ArrowUpRight, ReceiptText, UsersRound } from 'lucide-react'
import type { Transaction } from '../types'
import { formatMoney } from '../lib/money'

const categoryEmoji: Record<string, string> = {
  Groceries: '🛒',
  'Food & dining': '🍜',
  Transport: '🚕',
  Salary: '↙',
  Bills: '⌁',
  Entertainment: '🎬'
}

export function TransactionRow({ transaction, compact = false }: { transaction: Transaction; compact?: boolean }) {
  const isIncome = transaction.kind === 'credit'
  const date = new Intl.DateTimeFormat('en-IN', { day: 'numeric', month: 'short' }).format(new Date(`${transaction.occurredAt}T12:00:00`))
  return (
    <article className={`flex items-center gap-3 ${compact ? 'py-3' : 'py-4'}`}>
      <div className={`grid h-11 w-11 shrink-0 place-items-center rounded-2xl text-lg ${isIncome ? 'bg-moss-100 text-moss-800' : 'bg-[#f2f3ef] dark:bg-night-raised'}`} aria-hidden>
        {categoryEmoji[transaction.category] ?? <ReceiptText className="h-5 w-5" />}
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex items-start justify-between gap-3">
          <p className="truncate text-[15px] font-semibold text-ink">{transaction.merchant}</p>
          <p className={`shrink-0 text-[15px] font-bold ${isIncome ? 'text-moss-700' : 'text-ink'}`}>
            {isIncome ? '+' : '−'}{formatMoney(transaction.amountPaise)}
          </p>
        </div>
        <div className="mt-1 flex items-center justify-between gap-2 text-xs text-[#748079] tone-muted">
          <p className="flex min-w-0 items-center gap-1.5 truncate">
            {isIncome ? <ArrowDownLeft className="h-3 w-3" /> : <ArrowUpRight className="h-3 w-3" />}
            <span className="truncate">{transaction.category} · {transaction.account}</span>
          </p>
          <span className="shrink-0">{date}</span>
        </div>
        {transaction.memberSplits.length > 0 && (
          <div className="mt-2 flex items-center gap-1.5 text-[11px] font-semibold text-moss-700">
            <UsersRound className="h-3.5 w-3.5" /> Split with {transaction.memberSplits.map((split) => split.memberName).join(', ')} · your share {formatMoney(transaction.personalSharePaise)}
          </div>
        )}
      </div>
    </article>
  )
}

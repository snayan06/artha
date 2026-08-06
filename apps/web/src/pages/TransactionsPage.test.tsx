import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it } from 'vitest'
import type { Transaction } from '../types'
import { TransactionsPage } from './TransactionsPage'

const transactions: Transaction[] = [
  {
    id: 'expense', kind: 'debit', amountPaise: 50000, personalSharePaise: 50000,
    merchant: 'Groceries', category: 'Groceries', account: 'ICICI Bank',
    occurredAt: '2026-08-05', memberSplits: [], status: 'confirmed'
  },
  {
    id: 'transfer', kind: 'transfer', amountPaise: 2500000, personalSharePaise: 2500000,
    merchant: 'Self transfer', category: 'Transfer', account: 'ICICI Bank',
    destinationAccount: 'HDFC UPI', occurredAt: '2026-08-05', memberSplits: [],
    status: 'confirmed'
  },
  {
    id: 'card', kind: 'debit', amountPaise: 90000, personalSharePaise: 90000,
    merchant: 'Dinner', category: 'Food & dining', account: 'HDFC Card',
    occurredAt: '2026-08-04', memberSplits: [], status: 'confirmed'
  }
]

describe('TransactionsPage account activity filter', () => {
  afterEach(cleanup)

  it('includes both sides of a transfer when filtering by account', async () => {
    const user = userEvent.setup()
    render(<TransactionsPage transactions={transactions} demoMode={false} />)

    await user.selectOptions(screen.getByRole('combobox', { name: 'Filter by account' }), 'HDFC UPI')

    expect(screen.getByText('Self transfer')).toBeInTheDocument()
    expect(screen.queryByText('Groceries')).not.toBeInTheDocument()
    expect(screen.getByText('1 transaction')).toBeInTheDocument()
  })

  it('searches destination account names', async () => {
    const user = userEvent.setup()
    render(<TransactionsPage transactions={transactions} demoMode={false} />)

    await user.type(screen.getByLabelText('Search transactions'), 'HDFC UPI')

    expect(screen.getByText('Self transfer')).toBeInTheDocument()
    expect(screen.queryByText('Dinner')).not.toBeInTheDocument()
  })
})

import { cleanup, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
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

  it('debounces database search so older matching notes are discoverable', async () => {
    const user = userEvent.setup()
    const older = {
      ...transactions[0],
      id: 'older-note',
      merchant: 'Zomato',
      note: 'Team dinner',
      occurredAt: '2024-01-01'
    }
    const onSearch = vi.fn().mockResolvedValue([older])
    render(
      <TransactionsPage
        transactions={transactions}
        demoMode={false}
        onSearch={onSearch}
      />
    )

    await user.type(screen.getByLabelText('Search transactions'), 'team dinner')

    await waitFor(() => expect(onSearch).toHaveBeenCalledWith('team dinner'))
    expect(await screen.findByText('Zomato')).toBeInTheDocument()
    expect(screen.getByText('1 transaction')).toBeInTheDocument()
  })

  it('loads older activity through the stable cursor path', async () => {
    const user = userEvent.setup()
    const onLoadMore = vi.fn().mockResolvedValue(undefined)
    render(
      <TransactionsPage
        transactions={transactions}
        demoMode={false}
        hasMore
        onLoadMore={onLoadMore}
      />
    )

    await user.click(screen.getByRole('button', { name: 'Load older activity' }))

    await waitFor(() => expect(onLoadMore).toHaveBeenCalledTimes(1))
  })

  it('opens a saved transaction and submits an explicit correction', async () => {
    const user = userEvent.setup()
    const onUpdate = vi.fn().mockResolvedValue(undefined)
    render(
      <TransactionsPage
        transactions={transactions}
        demoMode={false}
        selectedTransactionId="expense"
        onUpdate={onUpdate}
        onVoid={vi.fn()}
      />
    )

    const dialog = screen.getByRole('dialog', { name: /transaction details/i })
    expect(dialog).toBeInTheDocument()
    expect(within(dialog).getByText('ICICI Bank')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /edit transaction/i }))
    await user.clear(screen.getByLabelText('Amount in rupees'))
    await user.type(screen.getByLabelText('Amount in rupees'), '625')
    await user.type(screen.getByLabelText('Why are you correcting this?'), 'Wrong amount')
    await user.click(screen.getByRole('button', { name: /save correction/i }))

    await waitFor(() => expect(onUpdate).toHaveBeenCalledTimes(1))
    expect(onUpdate.mock.calls[0]?.[0]).toBe('expense')
    expect(onUpdate.mock.calls[0]?.[1]).toMatchObject({ amountPaise: 62500 })
    expect(onUpdate.mock.calls[0]?.[2]).toBe('Wrong amount')
  })

  it('requires a reason before removing a transaction from totals', async () => {
    const user = userEvent.setup()
    const onVoid = vi.fn().mockResolvedValue(undefined)
    render(
      <TransactionsPage
        transactions={transactions}
        demoMode={false}
        selectedTransactionId="card"
        onUpdate={vi.fn()}
        onVoid={onVoid}
      />
    )

    await user.click(screen.getByRole('button', { name: /remove from totals/i }))
    const remove = screen.getByRole('button', { name: /confirm removal/i })
    expect(remove).toBeDisabled()
    await user.type(screen.getByLabelText('Why are you removing this?'), 'Duplicate entry')
    await user.click(remove)

    await waitFor(() => expect(onVoid).toHaveBeenCalledWith('card', 'Duplicate entry'))
  })

  it('shows a repayment as read-only ledger history rather than editable spending', () => {
    const settlement = {
      id: 'settlement', kind: 'settlement', movementDirection: 'in',
      amountPaise: 4_000, personalSharePaise: 0, merchant: 'Repayment from Harmi',
      category: 'Shared repayment', account: 'ICICI Bank', occurredAt: '2026-08-10',
      memberSplits: [], status: 'confirmed'
    } as unknown as Transaction
    render(
      <TransactionsPage
        transactions={[settlement]}
        demoMode={false}
        selectedTransactionId="settlement"
        onUpdate={vi.fn()}
        onVoid={vi.fn()}
      />
    )

    const dialog = screen.getByRole('dialog', { name: /transaction details/i })
    expect(within(dialog).getAllByText('Shared repayment')).toHaveLength(2)
    expect(within(dialog).queryByRole('button', { name: /edit transaction/i })).not.toBeInTheDocument()
    expect(within(dialog).queryByRole('button', { name: /remove from totals/i })).not.toBeInTheDocument()
  })
})

import type { Dashboard, Transaction } from '../types'

export const demoTransactions: Transaction[] = [
  {
    id: 'tx-001', kind: 'debit', amountPaise: 184000, personalSharePaise: 92000,
    merchant: 'Reliance Fresh', category: 'Groceries', account: 'HDFC UPI',
    occurredAt: '2026-08-03', memberSplits: [{ memberId: 'demo-member', memberName: 'Shared member', amountPaise: 92000 }], status: 'confirmed'
  },
  {
    id: 'tx-002', kind: 'credit', amountPaise: 18500000, personalSharePaise: 18500000,
    merchant: 'Monthly salary', category: 'Salary', account: 'ICICI Bank',
    occurredAt: '2026-08-01', memberSplits: [], status: 'confirmed'
  },
  {
    id: 'tx-003', kind: 'debit', amountPaise: 62000, personalSharePaise: 62000,
    merchant: 'Indian Coffee House', category: 'Food & dining', account: 'HDFC UPI',
    occurredAt: '2026-07-31', memberSplits: [], status: 'confirmed'
  },
  {
    id: 'tx-004', kind: 'debit', amountPaise: 28400, personalSharePaise: 28400,
    merchant: 'Uber', category: 'Transport', account: 'HDFC Card',
    occurredAt: '2026-07-30', memberSplits: [], status: 'confirmed'
  },
  {
    id: 'tx-005', kind: 'debit', amountPaise: 240000, personalSharePaise: 120000,
    merchant: 'Mekong Folks', category: 'Food & dining', account: 'ICICI Bank',
    occurredAt: '2026-07-27', memberSplits: [{ memberId: 'demo-member', memberName: 'Shared member', amountPaise: 120000 }], status: 'confirmed'
  },
  {
    id: 'tx-006', kind: 'debit', amountPaise: 149900, personalSharePaise: 149900,
    merchant: 'JioFiber', category: 'Bills', account: 'HDFC Card',
    occurredAt: '2026-07-24', memberSplits: [], status: 'confirmed'
  }
]

export const demoDashboard: Dashboard = {
  availablePaise: 4286500,
  incomePaise: 18500000,
  spendPaise: 2134200,
  sharedBalancePaise: 212000,
  memberBalances: [{ id: 'demo-member', name: 'Shared member', balancePaise: 212000, status: 'owes you' }],
  monthly: [
    { month: 'Mar', incomePaise: 16000000, spendPaise: 5840000 },
    { month: 'Apr', incomePaise: 16000000, spendPaise: 6930000 },
    { month: 'May', incomePaise: 17000000, spendPaise: 5150000 },
    { month: 'Jun', incomePaise: 17000000, spendPaise: 7410000 },
    { month: 'Jul', incomePaise: 17500000, spendPaise: 6280000 },
    { month: 'Aug', incomePaise: 18500000, spendPaise: 2134200 }
  ],
  recentTransactions: demoTransactions.slice(0, 4)
}

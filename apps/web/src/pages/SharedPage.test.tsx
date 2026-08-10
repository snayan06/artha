import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { SharedPage } from './SharedPage'

describe('SharedPage settlement workflow', () => {
  afterEach(cleanup)

  it('records a reviewed repayment against a specific account', async () => {
    const user = userEvent.setup()
    const onSettle = vi.fn().mockResolvedValue(undefined)
    render(
      <SharedPage
        transactions={[]}
        sharedBalancePaise={4_000}
        memberBalances={[{ id: 'member-1', name: 'Family member', balancePaise: 4_000, status: 'owes you' }]}
        demoMode={false}
        profile={{ displayName: 'You', householdName: 'Home', members: [], isDemo: false }}
        accounts={[{ id: 'account-1', name: 'ICICI Bank', kind: 'bank' }]}
        onSettle={onSettle}
      />
    )

    await user.click(screen.getByRole('button', { name: /record repayment with family member/i }))
    expect(screen.getByRole('dialog', { name: /record repayment/i })).toBeInTheDocument()
    expect(screen.getByText(/without counting it as income or spending/i)).toBeInTheDocument()
    await user.clear(screen.getByLabelText('Amount in rupees'))
    await user.type(screen.getByLabelText('Amount in rupees'), '25')
    await user.selectOptions(screen.getByLabelText('Account where money moved'), 'account-1')
    await user.type(screen.getByLabelText('Note (optional)'), 'Partial repayment')
    await user.click(screen.getByRole('button', { name: /confirm repayment/i }))

    await waitFor(() => expect(onSettle).toHaveBeenCalledTimes(1))
    expect(onSettle).toHaveBeenCalledWith(expect.objectContaining({
      memberId: 'member-1', accountId: 'account-1', amountPaise: 2_500, note: 'Partial repayment'
    }))
  })

  it('does not claim everyone is settled when individual balances only net to zero', () => {
    render(
      <SharedPage
        transactions={[]}
        sharedBalancePaise={0}
        memberBalances={[
          { id: 'member-1', name: 'Harmi', balancePaise: 4_000, status: 'owes you' },
          { id: 'member-2', name: 'Family member', balancePaise: -4_000, status: 'you owe' }
        ]}
        demoMode={false}
        profile={{ displayName: 'You', householdName: 'Home', members: [], isDemo: false }}
        accounts={[{ id: 'account-1', name: 'ICICI Bank', kind: 'bank' }]}
        onSettle={vi.fn()}
      />
    )

    expect(screen.queryByText('Everyone is settled up')).not.toBeInTheDocument()
    expect(screen.getByText('Individual balances still need settling')).toBeInTheDocument()
  })
})

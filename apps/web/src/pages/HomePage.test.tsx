import { cleanup, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { demoDashboard } from '../data/demo'
import * as api from '../lib/api'
import { RouterProvider } from '../lib/router'
import { HomePage } from './HomePage'

describe('HomePage quick capture', () => {
  beforeEach(() => {
    vi.spyOn(api, 'routeIntent').mockResolvedValue({ intent: 'capture_transaction' })
  })

  it('explains the AI routing boundary at the new Home entry surface', () => {
    render(
      <RouterProvider>
        <HomePage dashboard={demoDashboard} demoMode profile={{ displayName: 'You', householdName: 'My household', members: [], isDemo: true }} />
      </RouterProvider>,
    )

    expect(screen.getByRole('note', { name: /AI-assisted routing/i })).toHaveTextContent(/never saves.*automatically/i)
  })

  afterEach(() => {
    cleanup()
    vi.restoreAllMocks()
    window.history.replaceState(null, '', '/')
  })

  it('passes the sentence directly to Quick Add route state', async () => {
    const user = userEvent.setup()
    render(
      <RouterProvider>
        <HomePage dashboard={demoDashboard} demoMode profile={{ displayName: 'You', householdName: 'My household', members: [], isDemo: true }} />
      </RouterProvider>,
    )

    const capture = 'Paid 1840 for groceries from HDFC UPI, split equally with Sam'
    await user.type(screen.getByLabelText(/add a transaction or ask artha/i), capture)
    await user.click(screen.getByRole('button', { name: /continue/i }))

    expect(window.location.pathname).toBe('/add')
    expect(window.history.state).toEqual({ capture })
  })

  it('hands a ledger question directly to Ask Artha', async () => {
    vi.mocked(api.routeIntent).mockResolvedValue({ intent: 'ask_ledger' })
    const user = userEvent.setup()
    render(
      <RouterProvider>
        <HomePage dashboard={demoDashboard} demoMode profile={{ displayName: 'You', householdName: 'My household', members: [], isDemo: true }} />
      </RouterProvider>,
    )

    const question = 'Show my spending trend for the last three months'
    await user.type(screen.getByLabelText(/add a transaction or ask artha/i), question)
    await user.click(screen.getByRole('button', { name: /continue/i }))

    expect(window.location.pathname).toBe('/assistant')
    expect(window.history.state).toEqual(expect.objectContaining({ initialQuestion: question }))
    expect(window.history.state.handoffId).toEqual(expect.any(String))
  })

  it('provides chart values without relying on color or hover', () => {
    render(
      <RouterProvider>
        <HomePage dashboard={demoDashboard} demoMode profile={{ displayName: 'You', householdName: 'My household', members: [], isDemo: true }} />
      </RouterProvider>,
    )

    const chartTable = screen.getByRole('table', { name: 'Six-month income and spending values' })
    expect(within(chartTable).getAllByRole('row')).toHaveLength(demoDashboard.monthly.length + 1)
    expect(within(chartTable).getByRole('columnheader', { name: 'Income' })).toBeInTheDocument()
  })

  it('shows a useful chart empty state', () => {
    render(
      <RouterProvider>
        <HomePage dashboard={{ ...demoDashboard, monthly: [] }} demoMode profile={{ displayName: 'You', householdName: 'My household', members: [], isDemo: true }} />
      </RouterProvider>,
    )

    expect(screen.getByRole('status')).toHaveTextContent('No monthly activity to chart yet')
  })
})

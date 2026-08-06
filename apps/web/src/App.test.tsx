import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { demoDashboard, demoTransactions } from './data/demo'
import { RouterProvider } from './lib/router'

const api = vi.hoisted(() => ({
  ApiError: class ApiError extends Error {
    readonly status: number

    constructor(status: number, message: string) {
      super(message)
      this.status = status
    }
  },
  bootstrapDemo: vi.fn(),
  getMembers: vi.fn(),
  setupOnboarding: vi.fn(),
  getDashboard: vi.fn(),
  getTransactions: vi.fn(),
  confirmDraft: vi.fn()
}))

vi.mock('./lib/api', () => api)

import App, { LedgerLoadError, ledgerLoadIssue } from './App'

describe('first-run gate', () => {
  beforeEach(() => {
    api.bootstrapDemo.mockResolvedValue(undefined)
    api.getMembers.mockResolvedValue([{ id: '7', name: 'Demo member' }])
    api.getDashboard.mockResolvedValue({ data: demoDashboard, demo: true })
    api.getTransactions.mockResolvedValue({ data: demoTransactions, demo: true })
  })
  afterEach(() => {
    cleanup()
    localStorage.clear()
    vi.clearAllMocks()
  })

  it('does not bootstrap until the user explicitly chooses the fictional demo', async () => {
    const user = userEvent.setup()
    render(<RouterProvider><App /></RouterProvider>)
    expect(screen.getByRole('heading', { name: 'Where does your money live?' })).toBeInTheDocument()
    expect(api.bootstrapDemo).not.toHaveBeenCalled()

    await user.click(screen.getByRole('button', { name: 'Explore fictional demo' }))
    await waitFor(() => expect(api.bootstrapDemo).toHaveBeenCalledTimes(1))
    expect(localStorage.getItem('artha.setup.complete')).toBe('true')
    expect(await screen.findByRole('heading', { name: 'Your money, made clear.' })).toBeInTheDocument()
  })
})

describe('ledger recovery states', () => {
  afterEach(() => cleanup())

  it('explains a missing production RPC without implying that data was lost', () => {
    const issue = ledgerLoadIssue(new api.ApiError(404, 'missing function'), 'ledger')

    expect(issue).toMatchObject({
      title: 'Artha is finishing an update',
      retryLabel: 'Try again'
    })
    expect(issue.message).toContain('Your data is safe')
  })

  it('renders actionable mobile-safe recovery controls and retries once', async () => {
    const user = userEvent.setup()
    const retry = vi.fn().mockResolvedValue(undefined)
    const signOut = vi.fn().mockResolvedValue(undefined)
    const issue = ledgerLoadIssue(new api.ApiError(503, 'unavailable'), 'ledger')

    render(<LedgerLoadError issue={issue} onRetry={retry} onSignOut={signOut} />)

    expect(screen.getByRole('heading', { name: 'Artha is taking longer than expected' })).toBeInTheDocument()
    expect(screen.getByRole('alert')).toHaveTextContent('Your data is safe')
    await user.click(screen.getByRole('button', { name: 'Retry connection' }))
    expect(retry).toHaveBeenCalledTimes(1)
    expect(screen.getByRole('button', { name: 'Sign out' })).toBeInTheDocument()
  })
})

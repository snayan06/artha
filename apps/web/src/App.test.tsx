import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { demoDashboard, demoTransactions } from './data/demo'
import { RouterProvider } from './lib/router'

const api = vi.hoisted(() => ({
  bootstrapDemo: vi.fn(),
  getMembers: vi.fn(),
  setupOnboarding: vi.fn(),
  getDashboard: vi.fn(),
  getTransactions: vi.fn(),
  confirmDraft: vi.fn()
}))

vi.mock('./lib/api', () => api)

import App from './App'

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
    Object.values(api).forEach((mock) => mock.mockClear())
  })

  it('does not bootstrap until the user explicitly chooses the fictional demo', async () => {
    const user = userEvent.setup()
    render(<RouterProvider><App /></RouterProvider>)
    expect(screen.getByRole('heading', { name: 'Where does your money live?' })).toBeInTheDocument()
    expect(api.bootstrapDemo).not.toHaveBeenCalled()

    await user.click(screen.getByRole('button', { name: 'Explore fictional demo' }))
    await waitFor(() => expect(api.bootstrapDemo).toHaveBeenCalledTimes(1))
    expect(localStorage.getItem('hisab.setup.complete')).toBe('true')
    expect(await screen.findByRole('heading', { name: 'Your money, made clear.' })).toBeInTheDocument()
  })
})

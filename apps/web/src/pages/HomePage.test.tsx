import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it } from 'vitest'
import { demoDashboard } from '../data/demo'
import { RouterProvider } from '../lib/router'
import { HomePage } from './HomePage'

describe('HomePage quick capture', () => {
  afterEach(() => window.history.replaceState(null, '', '/'))

  it('passes the sentence directly to Quick Add route state', async () => {
    const user = userEvent.setup()
    render(
      <RouterProvider>
        <HomePage dashboard={demoDashboard} demoMode profile={{ displayName: 'You', householdName: 'My household', members: [] }} />
      </RouterProvider>,
    )

    const capture = 'Paid 1840 for groceries from HDFC UPI, split equally with Sam'
    await user.type(screen.getByLabelText(/describe a transaction/i), capture)
    await user.click(screen.getByRole('button', { name: /make draft/i }))

    expect(window.location.pathname).toBe('/add')
    expect(window.history.state).toEqual({ capture })
  })
})

import { act, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { RouterProvider } from '../lib/router'
import { Shell } from './Shell'

function setOnline(value: boolean) {
  Object.defineProperty(navigator, 'onLine', { configurable: true, value })
}

describe('Shell network status', () => {
  afterEach(() => setOnline(true))

  it('explains that changes cannot be saved while offline', () => {
    setOnline(false)
    render(<RouterProvider><Shell><p>Ledger</p></Shell></RouterProvider>)

    expect(screen.getByRole('status')).toHaveTextContent('new changes cannot be saved until you reconnect')
  })

  it('clears the offline warning after reconnection', () => {
    setOnline(false)
    render(<RouterProvider><Shell><p>Ledger</p></Shell></RouterProvider>)

    act(() => window.dispatchEvent(new Event('online')))

    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })
})

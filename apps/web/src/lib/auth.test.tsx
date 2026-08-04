import { act, cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { AuthChangeEvent, Session } from '@supabase/supabase-js'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { RouterProvider } from './router'

const supabase = vi.hoisted(() => {
  const getSession = vi.fn()
  const signInWithOtp = vi.fn()
  const signOut = vi.fn()
  const refreshSession = vi.fn()
  let authCallback: ((event: AuthChangeEvent, session: Session | null) => void) | undefined
  const unsubscribe = vi.fn()
  const client = {
    auth: {
      getSession,
      signInWithOtp,
      signOut,
      refreshSession,
      onAuthStateChange: vi.fn((callback: typeof authCallback) => {
        authCallback = callback
        return { data: { subscription: { unsubscribe } } }
      })
    }
  }
  return { getSession, signInWithOtp, signOut, refreshSession, unsubscribe, client, callback: () => authCallback }
})

vi.mock('@supabase/supabase-js', () => ({ createClient: vi.fn(() => supabase.client) }))

import App from '../App'
import { AuthProvider, useAuth } from './auth'

function session(token: string): Session {
  return {
    access_token: token,
    refresh_token: `refresh-${token}`,
    expires_in: 3600,
    token_type: 'bearer',
    user: { id: 'user-1', aud: 'authenticated', role: 'authenticated', email: 'ari@example.com', app_metadata: {}, user_metadata: {}, created_at: '2026-08-04T00:00:00Z' }
  } as Session
}

function AuthProbe() {
  const auth = useAuth()
  return <div><span>{auth.status}</span><span>{auth.session?.access_token ?? 'none'}</span><button onClick={() => void auth.refreshSession()}>Refresh</button><button onClick={() => void auth.signOut()}>Sign out</button></div>
}

function createMemoryStorage(): Storage {
  const values = new Map<string, string>()

  return {
    get length() {
      return values.size
    },
    clear: () => values.clear(),
    getItem: (key) => values.get(key) ?? null,
    key: (index) => [...values.keys()][index] ?? null,
    removeItem: (key) => values.delete(key),
    setItem: (key, value) => values.set(key, String(value))
  }
}

describe('Supabase auth provider', () => {
  let storage: Storage

  beforeEach(() => {
    storage = createMemoryStorage()
    Object.defineProperty(globalThis, 'localStorage', { configurable: true, value: storage })
    Object.defineProperty(window, 'localStorage', { configurable: true, value: storage })
    vi.stubEnv('VITE_DEMO_MODE', 'false')
    vi.stubEnv('VITE_SUPABASE_URL', 'https://project.supabase.co')
    vi.stubEnv('VITE_SUPABASE_ANON_KEY', 'public-anon-key')
    supabase.getSession.mockResolvedValue({ data: { session: null }, error: null })
    supabase.signInWithOtp.mockResolvedValue({ data: {}, error: null })
    supabase.signOut.mockResolvedValue({ error: null })
    supabase.refreshSession.mockResolvedValue({ data: { session: null }, error: null })
  })

  afterEach(() => {
    cleanup()
    storage.clear()
    vi.unstubAllEnvs()
    vi.clearAllMocks()
  })

  it('shows an accessible magic-link gate and sends the redirect to this origin', async () => {
    const user = userEvent.setup()
    render(<AuthProvider><RouterProvider><App /></RouterProvider></AuthProvider>)

    expect(await screen.findByRole('heading', { name: 'Sign in to your ledger' })).toBeInTheDocument()
    await user.type(screen.getByLabelText('Email address'), 'ari@example.com')
    await user.click(screen.getByRole('button', { name: 'Email me a sign-in link' }))

    await waitFor(() => expect(supabase.signInWithOtp).toHaveBeenCalledWith({
      email: 'ari@example.com',
      options: { emailRedirectTo: window.location.origin }
    }))
    expect(screen.getByRole('status')).toHaveTextContent('Check your email')
  })

  it('loads, refreshes, observes and signs out of the persisted session', async () => {
    const firstSession = session('token-one')
    const secondSession = session('token-two')
    supabase.getSession.mockResolvedValue({ data: { session: firstSession }, error: null })
    supabase.refreshSession.mockResolvedValue({ data: { session: secondSession }, error: null })
    render(<AuthProvider><AuthProbe /></AuthProvider>)

    expect(await screen.findByText('authenticated')).toBeInTheDocument()
    expect(screen.getByText('token-one')).toBeInTheDocument()

    await act(async () => supabase.callback()?.('TOKEN_REFRESHED', secondSession))
    expect(screen.getByText('token-two')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Refresh' }))
    await waitFor(() => expect(supabase.refreshSession).toHaveBeenCalledTimes(1))

    await userEvent.click(screen.getByRole('button', { name: 'Sign out' }))
    await waitFor(() => expect(supabase.signOut).toHaveBeenCalledTimes(1))
  })
})

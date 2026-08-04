/* eslint-disable react-refresh/only-export-components */
import { createClient, type Session, type SupabaseClient, type User } from '@supabase/supabase-js'
import { createContext, type ReactNode, useContext, useEffect, useMemo, useState } from 'react'
import { configureApiAccessTokenProvider } from './api'

export type AuthStatus = 'demo' | 'loading' | 'authenticated' | 'unauthenticated' | 'error'

interface AuthContextValue {
  status: AuthStatus
  session: Session | null
  user: User | null
  error: string | null
  signInWithMagicLink: (email: string) => Promise<void>
  signOut: () => Promise<void>
  refreshSession: () => Promise<void>
}

const demoAuth: AuthContextValue = {
  status: 'demo',
  session: null,
  user: null,
  error: null,
  signInWithMagicLink: async () => undefined,
  signOut: async () => undefined,
  refreshSession: async () => undefined
}

const AuthContext = createContext<AuthContextValue>(demoAuth)
let supabaseClient: SupabaseClient | null = null

export function isDemoMode(): boolean {
  return import.meta.env.VITE_DEMO_MODE !== 'false'
}

function authConfiguration(): { url: string; anonKey: string } | null {
  const url = (import.meta.env.VITE_SUPABASE_URL as string | undefined)?.trim()
  const anonKey = (import.meta.env.VITE_SUPABASE_ANON_KEY as string | undefined)?.trim()
  return url && anonKey ? { url, anonKey } : null
}

function getSupabaseClient(): SupabaseClient | null {
  const configuration = authConfiguration()
  if (!configuration) return null
  if (!supabaseClient) {
    supabaseClient = createClient(configuration.url, configuration.anonKey, {
      auth: {
        persistSession: true,
        autoRefreshToken: true,
        detectSessionInUrl: true,
        flowType: 'pkce',
        storageKey: 'hisab.auth'
      }
    })
  }
  return supabaseClient
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const demo = isDemoMode()
  const [status, setStatus] = useState<AuthStatus>(demo ? 'demo' : 'loading')
  const [session, setSession] = useState<Session | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (demo) {
      configureApiAccessTokenProvider(async () => null)
      setStatus('demo')
      setSession(null)
      setError(null)
      return
    }

    const client = getSupabaseClient()
    if (!client) {
      configureApiAccessTokenProvider(async () => null)
      setStatus('error')
      setError('Supabase authentication is not configured for this deployment.')
      return
    }

    let active = true
    configureApiAccessTokenProvider(async () => {
      const { data, error: sessionError } = await client.auth.getSession()
      if (sessionError) return null
      return data.session?.access_token ?? null
    })

    void client.auth.getSession().then(({ data, error: sessionError }) => {
      if (!active) return
      if (sessionError) {
        setStatus('error')
        setError('Your session could not be loaded. Please sign in again.')
        return
      }
      setSession(data.session)
      setStatus(data.session ? 'authenticated' : 'unauthenticated')
      setError(null)
    })

    const { data: listener } = client.auth.onAuthStateChange((_event, nextSession) => {
      if (!active) return
      setSession(nextSession)
      setStatus(nextSession ? 'authenticated' : 'unauthenticated')
      setError(null)
    })

    return () => {
      active = false
      listener.subscription.unsubscribe()
      configureApiAccessTokenProvider(async () => null)
    }
  }, [demo])

  const value = useMemo<AuthContextValue>(() => ({
    status,
    session,
    user: session?.user ?? null,
    error,
    signInWithMagicLink: async (email: string) => {
      const client = getSupabaseClient()
      if (!client) throw new Error('Supabase authentication is not configured.')
      const { error: signInError } = await client.auth.signInWithOtp({
        email,
        options: { emailRedirectTo: window.location.origin }
      })
      if (signInError) throw new Error('The sign-in link could not be sent. Please try again.')
    },
    signOut: async () => {
      const client = getSupabaseClient()
      if (!client) return
      const { error: signOutError } = await client.auth.signOut()
      if (signOutError) throw new Error('Sign out failed. Please try again.')
    },
    refreshSession: async () => {
      const client = getSupabaseClient()
      if (!client) return
      const { data, error: refreshError } = await client.auth.refreshSession()
      if (refreshError) {
        setSession(null)
        setStatus('unauthenticated')
        throw new Error('Your session expired. Please sign in again.')
      }
      setSession(data.session)
      setStatus(data.session ? 'authenticated' : 'unauthenticated')
    }
  }), [error, session, status])

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  return useContext(AuthContext)
}

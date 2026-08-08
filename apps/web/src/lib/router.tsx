/* eslint-disable react-refresh/only-export-components */
import { createContext, type AnchorHTMLAttributes, type MouseEvent, type ReactNode, useContext, useEffect, useMemo, useState } from 'react'

export type AppPath = '/' | '/transactions' | '/shared' | '/assistant' | '/add' | '/settings'

interface RouterValue {
  path: AppPath
  state: unknown
  navigate: (path: AppPath, state?: unknown) => void
  back: () => void
}

const RouterContext = createContext<RouterValue | null>(null)

function cleanPath(pathname: string): AppPath {
  return pathname === '/transactions' || pathname === '/shared' || pathname === '/assistant' || pathname === '/add' || pathname === '/settings' ? pathname : '/'
}

export function RouterProvider({ children }: { children: ReactNode }) {
  const [location, setLocation] = useState(() => ({ path: cleanPath(window.location.pathname), state: window.history.state as unknown }))

  useEffect(() => {
    const update = () => setLocation({ path: cleanPath(window.location.pathname), state: window.history.state as unknown })
    window.addEventListener('popstate', update)
    return () => window.removeEventListener('popstate', update)
  }, [])

  const value = useMemo<RouterValue>(() => ({
    ...location,
    navigate: (path, state) => {
      window.history.pushState(state ?? null, '', path)
      setLocation({ path, state })
      window.scrollTo({ top: 0, behavior: 'auto' })
    },
    back: () => window.history.back()
  }), [location])

  return <RouterContext.Provider value={value}>{children}</RouterContext.Provider>
}

export function useRouter(): RouterValue {
  const value = useContext(RouterContext)
  if (!value) throw new Error('useRouter must be used inside RouterProvider')
  return value
}

export function AppLink({ to, children, ...props }: { to: AppPath; children: ReactNode } & Omit<AnchorHTMLAttributes<HTMLAnchorElement>, 'href'>) {
  const { navigate } = useRouter()
  function follow(event: MouseEvent<HTMLAnchorElement>) {
    if (!event.metaKey && !event.ctrlKey && !event.shiftKey && event.button === 0) {
      event.preventDefault()
      navigate(to)
    }
  }
  return <a href={to} {...props} onClick={(event) => { props.onClick?.(event); if (!event.defaultPrevented) follow(event) }}>{children}</a>
}

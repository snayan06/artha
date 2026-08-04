import { Bot, CircleUserRound, Home, List, Plus, UsersRound } from 'lucide-react'
import type { ReactNode } from 'react'
import { type AppPath, useRouter } from '../lib/router'
import { ThemeControl } from './ThemeControl'

const navigation = [
  { to: '/' as AppPath, label: 'Home', icon: Home },
  { to: '/transactions' as AppPath, label: 'Transactions', icon: List },
  { to: '/shared' as AppPath, label: 'Shared', icon: UsersRound },
  { to: '/assistant' as AppPath, label: 'Assistant', icon: Bot }
]

export function Shell({ children }: { children: ReactNode }) {
  const { path, navigate } = useRouter()
  const isQuickAdd = path === '/add'

  return (
    <div className="min-h-screen bg-canvas text-ink">
      <header className="sticky top-0 z-30 border-b border-line/80 bg-canvas/90 backdrop-blur-xl dark:border-night-border dark:bg-night-canvas/95">
        <div className="mx-auto flex h-[72px] max-w-6xl items-center justify-between px-5 sm:px-8">
          <button onClick={() => navigate('/')} className="flex min-h-11 items-center gap-3 rounded-xl focus:outline-none focus-visible:ring-2 focus-visible:ring-moss-400" aria-label="Go home">
            <span className="grid h-9 w-9 place-items-center rounded-xl bg-moss-900 font-display text-lg font-bold text-white dark:bg-[#27604e]">H</span>
            <div className="text-left"><p className="font-display text-lg font-bold leading-none tracking-[-0.03em]">Hisab</p><p className="mt-1 text-[10px] font-semibold uppercase tracking-[0.16em] text-[#839089] tone-subtle">Private ledger</p></div>
          </button>
          <div className="flex items-center gap-2"><span className="hidden rounded-full bg-moss-100 px-3 py-1.5 text-xs font-semibold text-moss-800 sm:block">August overview</span><ThemeControl /><button className="grid h-11 w-11 place-items-center rounded-full border border-line bg-white text-[#66736d] tone-muted" aria-label="Open profile"><CircleUserRound className="h-5 w-5" /></button></div>
        </div>
      </header>

      <main className={`mx-auto max-w-6xl px-4 pb-32 pt-5 sm:px-8 sm:pt-8 ${isQuickAdd ? 'max-w-3xl' : ''}`}>{children}</main>

      {!isQuickAdd && (
        <nav className="safe-bottom fixed inset-x-0 bottom-0 z-40 border-t border-line bg-white/95 px-4 pt-2 backdrop-blur-xl dark:border-night-border dark:bg-night-surface/95 sm:left-1/2 sm:bottom-5 sm:w-[430px] sm:-translate-x-1/2 sm:rounded-[24px] sm:border sm:shadow-float" aria-label="Main navigation">
          <div className="relative grid grid-cols-5 items-end">
            {navigation.slice(0, 2).map((item) => <NavItem key={item.to} {...item} active={path === item.to} onClick={() => navigate(item.to)} />)}
            <div className="flex justify-center"><button onClick={() => navigate('/add')} className="-mt-7 grid h-14 w-14 place-items-center rounded-[20px] bg-moss-900 text-white shadow-float transition hover:-translate-y-0.5 focus:outline-none focus-visible:ring-2 focus-visible:ring-moss-400 focus-visible:ring-offset-2 dark:bg-[#27604e]" aria-label="Quick add transaction"><Plus className="h-6 w-6" strokeWidth={2.5} /></button></div>
            {navigation.slice(2).map((item) => <NavItem key={item.to} {...item} active={path === item.to} onClick={() => navigate(item.to)} />)}
          </div>
        </nav>
      )}
    </div>
  )
}

function NavItem({ label, icon: Icon, active, onClick }: (typeof navigation)[number] & { active: boolean; onClick: () => void }) {
  return <button onClick={onClick} className={`flex min-h-[54px] w-full flex-col items-center justify-center gap-1 rounded-xl text-[10px] font-semibold transition ${active ? 'text-moss-800' : 'text-[#8a958f] tone-subtle hover:text-moss-700'}`} aria-current={active ? 'page' : undefined}><Icon className={`h-5 w-5 ${active ? 'fill-moss-100' : ''}`} /><span>{label}</span></button>
}

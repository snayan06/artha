import { useCallback, useEffect, useState } from 'react'
import { Shell } from './components/Shell'
import { demoDashboard, demoTransactions } from './data/demo'
import { bootstrapDemo, confirmDraft, getDashboard, getMembers, getTransactions, getUserProfile, isOnboardingComplete, setupOnboarding } from './lib/api'
import { isDemoMode, useAuth } from './lib/auth'
import { useRouter } from './lib/router'
import { HomePage } from './pages/HomePage'
import { OnboardingPage } from './pages/OnboardingPage'
import { LoginPage, SessionLoadingPage } from './pages/LoginPage'
import { QuickAddPage } from './pages/QuickAddPage'
import { SharedPage } from './pages/SharedPage'
import { TransactionsPage } from './pages/TransactionsPage'
import { AssistantPage } from './pages/AssistantPage'
import type { AccountSetupInput, Dashboard, Transaction, TransactionDraft, UserProfile } from './types'

const SETUP_KEY = 'artha.setup.complete'
const PROFILE_KEY = 'artha.profile'
const defaultProfile: UserProfile = { displayName: 'You', householdName: 'My household', members: [] }
const emptyDashboard: Dashboard = {
  availablePaise: 0,
  incomePaise: 0,
  spendPaise: 0,
  sharedBalancePaise: 0,
  memberBalances: [],
  monthly: [],
  recentTransactions: []
}

function loadProfile(profileKey: string): UserProfile {
  try {
    const parsed = JSON.parse(localStorage.getItem(profileKey) ?? '{}') as Partial<UserProfile>
    return {
      displayName: parsed.displayName?.trim() || defaultProfile.displayName,
      householdName: parsed.householdName?.trim() || defaultProfile.householdName,
      members: Array.isArray(parsed.members) ? parsed.members.filter((member) => member && typeof member.id === 'string' && typeof member.name === 'string') : []
    }
  } catch {
    return defaultProfile
  }
}

function persistSetup(profile: UserProfile, profileKey: string, setupKey: string) {
  localStorage.setItem(profileKey, JSON.stringify(profile))
  localStorage.setItem(setupKey, 'true')
}

export default function App() {
  const auth = useAuth()
  if (auth.status === 'loading') return <SessionLoadingPage />
  if (auth.status === 'unauthenticated' || auth.status === 'error') {
    return <LoginPage configurationError={auth.status === 'error' ? auth.error : null} recovery={auth.recovery} onSendLink={auth.signInWithMagicLink} />
  }
  const userKey = auth.user?.id
  return <LedgerApp key={userKey ?? 'demo'} userKey={userKey} userEmail={auth.user?.email} onSignOut={auth.status === 'authenticated' ? auth.signOut : undefined} />
}

function LedgerApp({ userKey, userEmail, onSignOut }: { userKey?: string; userEmail?: string; onSignOut?: () => Promise<void> }) {
  const { path } = useRouter()
  const localDemo = isDemoMode()
  const setupKey = userKey ? `${SETUP_KEY}.${userKey}` : SETUP_KEY
  const profileKey = userKey ? `${PROFILE_KEY}.${userKey}` : PROFILE_KEY
  const [setupComplete, setSetupComplete] = useState(() => localDemo && localStorage.getItem(setupKey) === 'true')
  const [checkingSetup, setCheckingSetup] = useState(!localDemo)
  const [setupError, setSetupError] = useState('')
  const [profile, setProfile] = useState<UserProfile>(() => loadProfile(profileKey))
  const [dashboard, setDashboard] = useState<Dashboard>(() => localDemo ? demoDashboard : emptyDashboard)
  const [transactions, setTransactions] = useState<Transaction[]>(() => localDemo ? demoTransactions : [])
  const [demoMode, setDemoMode] = useState(localDemo)
  const [loadingLedger, setLoadingLedger] = useState(setupComplete)
  const [ledgerError, setLedgerError] = useState('')

  const checkSetup = useCallback(async () => {
    setCheckingSetup(true)
    setSetupError('')
    try {
      const complete = await isOnboardingComplete()
      if (complete) {
        setLoadingLedger(true)
        const serverProfile = await getUserProfile()
        setProfile(serverProfile)
        localStorage.setItem(profileKey, JSON.stringify(serverProfile))
      }
      setSetupComplete(complete)
    } catch {
      setSetupError('Artha could not verify your household setup. Check the connection and try again.')
    } finally {
      setCheckingSetup(false)
    }
  }, [profileKey])

  const refreshLedger = useCallback(async () => {
    setLoadingLedger(true)
    setLedgerError('')
    try {
      const [dashboardResponse, transactionsResponse] = await Promise.all([getDashboard(), getTransactions()])
      setDashboard(dashboardResponse.data)
      setTransactions(transactionsResponse.data)
      setDemoMode(dashboardResponse.demo || transactionsResponse.demo)
    } catch {
      setLedgerError('Artha could not load your ledger. No demo balances are being shown. Check the connection and try again.')
    } finally {
      setLoadingLedger(false)
    }
  }, [])

  useEffect(() => {
    if (setupComplete) void refreshLedger()
  }, [refreshLedger, setupComplete])

  useEffect(() => {
    if (!localDemo) void checkSetup()
  }, [checkSetup, localDemo])

  async function finishSetup(accounts: AccountSetupInput[], nextProfile: UserProfile) {
    const savedMembers = await setupOnboarding(
      accounts,
      nextProfile.members.map(({ name }) => ({ name })),
      nextProfile.displayName,
      nextProfile.householdName
    )
    const savedProfile = { ...nextProfile, members: savedMembers }
    persistSetup(savedProfile, profileKey, setupKey)
    setProfile(savedProfile)
    setLoadingLedger(true)
    setSetupComplete(true)
  }

  async function exploreDemo(nextProfile: UserProfile) {
    await bootstrapDemo()
    const demoMembers = await getMembers().catch(() => nextProfile.members)
    const demoProfile = { ...nextProfile, members: demoMembers }
    persistSetup(demoProfile, profileKey, setupKey)
    setProfile(demoProfile)
    setSetupComplete(true)
  }

  async function addTransaction(draft: TransactionDraft, idempotencyKey?: string): Promise<Transaction> {
    const transaction = await confirmDraft(draft, idempotencyKey)
    setTransactions((current) => [transaction, ...current])
    setDashboard((current) => ({
      ...current,
      availablePaise: current.availablePaise + (transaction.kind === 'transfer' ? 0 : transaction.kind === 'credit' ? transaction.amountPaise : -transaction.amountPaise),
      incomePaise: current.incomePaise + (transaction.kind === 'credit' ? transaction.amountPaise : 0),
      spendPaise: current.spendPaise + (transaction.kind === 'debit' ? transaction.personalSharePaise : 0),
      sharedBalancePaise: current.sharedBalancePaise + transaction.memberSplits.reduce((sum, split) => sum + split.amountPaise, 0),
      recentTransactions: [transaction, ...current.recentTransactions].slice(0, 4)
    }))
    return transaction
  }

  if (checkingSetup) return <SessionLoadingPage />
  if (setupError) return <LedgerLoadError message={setupError} onRetry={checkSetup} onSignOut={onSignOut} />
  if (!setupComplete) return <OnboardingPage onSave={finishSetup} onExploreDemo={exploreDemo} allowDemo={localDemo} />
  if (loadingLedger) return <SessionLoadingPage />
  if (ledgerError) return <LedgerLoadError message={ledgerError} onRetry={refreshLedger} onSignOut={onSignOut} />

  let page = <HomePage dashboard={dashboard} demoMode={demoMode} profile={profile} />
  if (path === '/transactions') page = <TransactionsPage transactions={transactions} demoMode={demoMode} />
  if (path === '/shared') page = <SharedPage transactions={transactions} sharedBalancePaise={dashboard.sharedBalancePaise} memberBalances={dashboard.memberBalances} demoMode={demoMode} profile={profile} />
  if (path === '/add') page = <QuickAddPage onConfirm={addTransaction} members={profile.members} />
  if (path === '/assistant') page = <AssistantPage />

  return <Shell userEmail={userEmail} onSignOut={onSignOut}>{page}</Shell>
}

function LedgerLoadError({ message, onRetry, onSignOut }: { message: string; onRetry: () => Promise<void>; onSignOut?: () => Promise<void> }) {
  return (
    <main className="grid min-h-screen place-items-center bg-canvas px-4 text-ink">
      <div className="w-full max-w-md rounded-[24px] border border-line bg-white p-6 text-center shadow-sm dark:bg-night-surface">
        <h1 className="font-display text-2xl font-bold">Your ledger is temporarily unavailable</h1>
        <p role="alert" className="mt-3 text-sm leading-6 text-[#6e7b74] tone-muted">{message}</p>
        <div className="mt-6 flex flex-col gap-3 sm:flex-row sm:justify-center">
          <button onClick={() => void onRetry()} className="min-h-11 rounded-xl bg-moss-900 px-5 text-sm font-semibold text-white">Try again</button>
          {onSignOut && <button onClick={() => void onSignOut()} className="min-h-11 rounded-xl border border-line px-5 text-sm font-semibold">Sign out</button>}
        </div>
      </div>
    </main>
  )
}

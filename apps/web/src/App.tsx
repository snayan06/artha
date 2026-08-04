import { useCallback, useEffect, useState } from 'react'
import { Shell } from './components/Shell'
import { demoDashboard, demoTransactions } from './data/demo'
import { bootstrapDemo, confirmDraft, getDashboard, getMembers, getTransactions, setupOnboarding } from './lib/api'
import { useRouter } from './lib/router'
import { HomePage } from './pages/HomePage'
import { OnboardingPage } from './pages/OnboardingPage'
import { QuickAddPage } from './pages/QuickAddPage'
import { SharedPage } from './pages/SharedPage'
import { TransactionsPage } from './pages/TransactionsPage'
import { AssistantPage } from './pages/AssistantPage'
import type { AccountSetupInput, Dashboard, Transaction, TransactionDraft, UserProfile } from './types'

const SETUP_KEY = 'hisab.setup.complete'
const PROFILE_KEY = 'hisab.profile'
const defaultProfile: UserProfile = { displayName: 'You', householdName: 'My household', members: [] }

function loadProfile(): UserProfile {
  try {
    const parsed = JSON.parse(localStorage.getItem(PROFILE_KEY) ?? '{}') as Partial<UserProfile>
    return {
      displayName: parsed.displayName?.trim() || defaultProfile.displayName,
      householdName: parsed.householdName?.trim() || defaultProfile.householdName,
      members: Array.isArray(parsed.members) ? parsed.members.filter((member) => member && typeof member.id === 'string' && typeof member.name === 'string') : []
    }
  } catch {
    return defaultProfile
  }
}

function persistSetup(profile: UserProfile) {
  localStorage.setItem(PROFILE_KEY, JSON.stringify(profile))
  localStorage.setItem(SETUP_KEY, 'true')
}

export default function App() {
  const { path } = useRouter()
  const [setupComplete, setSetupComplete] = useState(() => localStorage.getItem(SETUP_KEY) === 'true')
  const [profile, setProfile] = useState<UserProfile>(loadProfile)
  const [dashboard, setDashboard] = useState<Dashboard>(demoDashboard)
  const [transactions, setTransactions] = useState<Transaction[]>(demoTransactions)
  const [demoMode, setDemoMode] = useState(true)

  const refreshLedger = useCallback(async () => {
    const [dashboardResponse, transactionsResponse] = await Promise.all([getDashboard(), getTransactions()])
    setDashboard(dashboardResponse.data)
    setTransactions(transactionsResponse.data)
    setDemoMode(dashboardResponse.demo || transactionsResponse.demo)
  }, [])

  useEffect(() => {
    if (setupComplete) void refreshLedger()
  }, [refreshLedger, setupComplete])

  async function finishSetup(accounts: AccountSetupInput[], nextProfile: UserProfile) {
    const savedMembers = await setupOnboarding(accounts, nextProfile.members.map(({ name }) => ({ name })))
    const savedProfile = { ...nextProfile, members: savedMembers }
    persistSetup(savedProfile)
    setProfile(savedProfile)
    setSetupComplete(true)
  }

  async function exploreDemo(nextProfile: UserProfile) {
    await bootstrapDemo()
    const demoMembers = await getMembers().catch(() => nextProfile.members)
    const demoProfile = { ...nextProfile, members: demoMembers }
    persistSetup(demoProfile)
    setProfile(demoProfile)
    setSetupComplete(true)
  }

  async function addTransaction(draft: TransactionDraft): Promise<Transaction> {
    const transaction = await confirmDraft(draft)
    setTransactions((current) => [transaction, ...current])
    setDashboard((current) => ({
      ...current,
      availablePaise: current.availablePaise + (transaction.kind === 'credit' ? transaction.amountPaise : -transaction.amountPaise),
      incomePaise: current.incomePaise + (transaction.kind === 'credit' ? transaction.amountPaise : 0),
      spendPaise: current.spendPaise + (transaction.kind === 'debit' ? transaction.personalSharePaise : 0),
      sharedBalancePaise: current.sharedBalancePaise + transaction.memberSplits.reduce((sum, split) => sum + split.amountPaise, 0),
      recentTransactions: [transaction, ...current.recentTransactions].slice(0, 4)
    }))
    return transaction
  }

  if (!setupComplete) return <OnboardingPage onSave={finishSetup} onExploreDemo={exploreDemo} />

  let page = <HomePage dashboard={dashboard} demoMode={demoMode} profile={profile} />
  if (path === '/transactions') page = <TransactionsPage transactions={transactions} demoMode={demoMode} />
  if (path === '/shared') page = <SharedPage transactions={transactions} sharedBalancePaise={dashboard.sharedBalancePaise} memberBalances={dashboard.memberBalances} demoMode={demoMode} profile={profile} />
  if (path === '/add') page = <QuickAddPage onConfirm={addTransaction} members={profile.members} />
  if (path === '/assistant') page = <AssistantPage />

  return <Shell>{page}</Shell>
}

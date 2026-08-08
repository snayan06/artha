import { ChevronRight } from 'lucide-react'
import { useRef, useState, type ReactNode } from 'react'
import { routeIntent } from '../lib/api'
import { Button, Card } from './ui'

interface UnifiedEntryComposerProps {
  id: string
  value: string
  onChange: (value: string) => void
  onCapture: (message: string) => void | Promise<void>
  onAskLedger: (message: string) => void | Promise<void>
  placeholder: string
  accessibleLabel?: string
  variant?: 'compact' | 'full'
  secondaryAction?: ReactNode
}

type RecoveryState = 'clarify' | 'failure' | 'unsupported' | null

export function UnifiedEntryComposer({
  id,
  value,
  onChange,
  onCapture,
  onAskLedger,
  placeholder,
  accessibleLabel = 'Add a transaction or ask Artha',
  variant = 'compact',
  secondaryAction
}: UnifiedEntryComposerProps) {
  const [routing, setRouting] = useState(false)
  const [recovery, setRecovery] = useState<RecoveryState>(null)
  const generation = useRef(0)
  const inFlight = useRef(false)

  function normalizedMessage() {
    return value.trim()
  }

  function chooseCapture() {
    if (!normalizedMessage()) return
    generation.current += 1
    inFlight.current = false
    setRouting(false)
    setRecovery(null)
    void onCapture(value)
  }

  function chooseAssistant() {
    if (!normalizedMessage()) return
    generation.current += 1
    inFlight.current = false
    setRouting(false)
    setRecovery(null)
    void onAskLedger(value)
  }

  async function submit() {
    const message = normalizedMessage()
    if (!message || inFlight.current) return
    inFlight.current = true
    const requestGeneration = ++generation.current
    setRouting(true)
    setRecovery(null)
    try {
      const result = await routeIntent(message)
      if (generation.current !== requestGeneration) return
      if (result.intent === 'capture_transaction') {
        chooseCapture()
      } else if (result.intent === 'ask_ledger') {
        chooseAssistant()
      } else if (result.intent === 'clarify') {
        setRecovery('clarify')
      } else {
        setRecovery('unsupported')
      }
    } catch {
      if (generation.current === requestGeneration) setRecovery('failure')
    } finally {
      if (generation.current === requestGeneration) {
        inFlight.current = false
        setRouting(false)
      }
    }
  }

  function submitForm(event: React.FormEvent) {
    event.preventDefault()
    void submit()
  }

  function changeMessage(nextValue: string) {
    generation.current += 1
    inFlight.current = false
    setRouting(false)
    setRecovery(null)
    onChange(nextValue)
  }

  const fieldClassName = variant === 'full'
    ? 'w-full resize-none rounded-2xl border border-line bg-[#fafbf9] p-4 text-base leading-6 outline-none transition placeholder:text-[#a0aaa4] tone-subtle focus-visible:border-moss-400 focus-visible:ring-4 focus-visible:ring-moss-100 dark:bg-night-input'
    : 'min-h-12 min-w-0 flex-1 rounded-2xl border border-line bg-[#fafbf9] px-4 text-[15px] outline-none transition placeholder:text-[#9ca69f] tone-subtle focus-visible:border-moss-400 focus-visible:ring-4 focus-visible:ring-moss-100 dark:bg-night-input'

  return (
    <form onSubmit={submitForm}>
      <label className="sr-only" htmlFor={id}>{accessibleLabel}</label>
      <div className={variant === 'full' ? 'space-y-3' : 'flex flex-col gap-3 sm:flex-row'}>
        {variant === 'full' ? (
          <textarea
            id={id}
            name="unified-money-entry"
            autoComplete="off"
            rows={3}
            value={value}
            onChange={(event) => changeMessage(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
                event.preventDefault()
                void submit()
              }
            }}
            placeholder={placeholder}
            className={fieldClassName}
          />
        ) : (
          <input
            id={id}
            name="unified-money-entry"
            autoComplete="off"
            value={value}
            onChange={(event) => changeMessage(event.target.value)}
            placeholder={placeholder}
            className={fieldClassName}
          />
        )}
        <div className={variant === 'full' ? 'grid gap-2 sm:flex' : 'contents'}>
          <Button
            type="submit"
            disabled={!normalizedMessage()}
            loading={routing}
            className={variant === 'full' ? 'w-full sm:w-auto' : 'sm:px-6'}
          >
            Continue <ChevronRight className="h-4 w-4" aria-hidden="true" />
          </Button>
          {secondaryAction}
        </div>
      </div>

      {routing && <p role="status" aria-live="polite" className="mt-3 text-xs text-[#718078] tone-muted">Understanding your request…</p>}

      {(recovery === 'clarify' || recovery === 'failure') && (
        <Card className="mt-4 p-4 shadow-none" role={recovery === 'failure' ? 'alert' : undefined}>
          <p className="text-sm font-bold">
            {recovery === 'failure'
              ? 'Artha couldn’t route this automatically. Choose what you meant.'
              : 'What would you like Artha to do with this?'}
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            <Button type="button" variant="secondary" onClick={chooseCapture}>Add as transaction</Button>
            <Button type="button" variant="secondary" onClick={chooseAssistant}>Ask about my ledger</Button>
          </div>
        </Card>
      )}

      {recovery === 'unsupported' && (
        <p role="alert" className="mt-4 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-100">
          Artha can currently add transactions or answer questions about your ledger. Try rephrasing your request.
        </p>
      )}
    </form>
  )
}

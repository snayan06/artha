import { type ButtonHTMLAttributes, type HTMLAttributes, type ReactNode } from 'react'
import { LoaderCircle } from 'lucide-react'
import { twMerge } from 'tailwind-merge'

export function Card({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={twMerge('rounded-[24px] border border-line bg-white shadow-card dark:border-night-border dark:bg-night-surface', className)} {...props} />
}

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'ghost'
  loading?: boolean
  icon?: ReactNode
}

export function Button({ className, variant = 'primary', loading, icon, children, disabled, ...props }: ButtonProps) {
  const variants = {
    primary: 'bg-moss-900 text-white hover:bg-moss-800 shadow-[0_8px_20px_rgba(23,63,53,.18)] dark:bg-[#27604e] dark:hover:bg-[#31745f]',
    secondary: 'border border-line bg-white text-ink hover:border-moss-300 hover:bg-moss-50 dark:border-night-border dark:bg-night-surface dark:hover:bg-night-raised',
    ghost: 'text-moss-800 hover:bg-moss-50'
  }
  return (
    <button
      className={twMerge('inline-flex min-h-11 items-center justify-center gap-2 rounded-2xl px-4 text-sm font-semibold transition focus:outline-none focus-visible:ring-2 focus-visible:ring-moss-400 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50', variants[variant], className)}
      disabled={disabled || loading}
      {...props}
    >
      {loading ? <LoaderCircle className="h-4 w-4 animate-spin motion-reduce:animate-none" aria-hidden="true" /> : icon}
      {children}
    </button>
  )
}

export function Badge({ children, tone = 'neutral' }: { children: ReactNode; tone?: 'neutral' | 'green' | 'amber' }) {
  const tones = {
    neutral: 'bg-[#f0f2ee] text-[#52605a] tone-muted dark:bg-night-raised dark:text-night-muted',
    green: 'bg-moss-100 text-moss-800',
    amber: 'bg-amber-50 text-amber-800 dark:bg-[#3a3020] dark:text-[#f0c879]'
  }
  return <span className={`inline-flex items-center rounded-full px-2.5 py-1 text-[11px] font-semibold ${tones[tone]}`}>{children}</span>
}

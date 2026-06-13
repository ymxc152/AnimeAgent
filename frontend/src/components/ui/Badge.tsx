import type { ReactNode } from 'react'

interface BadgeProps {
  children: ReactNode
  variant?:
    | 'default'
    | 'success'
    | 'warning'
    | 'danger'
    | 'info'
    | 'muted'
    | 'primary'
    | 'outline'
  size?: 'sm' | 'md'
  className?: string
}

export function Badge({
  children,
  variant = 'default',
  size = 'sm',
  className = '',
}: BadgeProps) {
  const variants: Record<string, string> = {
    default: 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300',
    primary:
      'bg-indigo-100 text-indigo-700 dark:bg-indigo-500/15 dark:text-indigo-300',
    success:
      'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300',
    warning:
      'bg-amber-100 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300',
    danger:
      'bg-rose-100 text-rose-700 dark:bg-rose-500/15 dark:text-rose-300',
    info: 'bg-sky-100 text-sky-700 dark:bg-sky-500/15 dark:text-sky-300',
    muted: 'bg-slate-50 text-slate-500 dark:bg-slate-900 dark:text-slate-500',
    outline:
      'border border-slate-200 bg-transparent text-slate-600 dark:border-slate-700 dark:text-slate-400',
  }

  const sizes = {
    sm: 'px-2 py-0.5 text-xs',
    md: 'px-2.5 py-1 text-sm',
  }

  return (
    <span
      className={`inline-flex items-center rounded-full font-medium ${variants[variant]} ${sizes[size]} ${className}`}
    >
      {children}
    </span>
  )
}

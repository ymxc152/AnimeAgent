import type { ReactNode } from 'react'

interface CardProps {
  children: ReactNode
  className?: string
  padding?: 'none' | 'sm' | 'md' | 'lg'
  hover?: boolean
  onClick?: () => void
}

export function Card({ children, className = '', padding = 'md', hover = false, onClick }: CardProps) {
  const paddings = {
    none: '',
    sm: 'p-4',
    md: 'p-6',
    lg: 'p-8',
  }

  return (
    <div
      onClick={onClick}
      className={`
        rounded-2xl border border-slate-200/60 bg-white/80 backdrop-blur-xl
        dark:border-slate-700/60 dark:bg-slate-900/80
        shadow-sm shadow-slate-200/50 dark:shadow-slate-950/50
        ${hover ? 'transition-all duration-200 hover:-translate-y-0.5 hover:shadow-lg hover:shadow-slate-200/60 dark:hover:shadow-slate-950/60' : ''}
        ${paddings[padding]} ${className}
      `}
    >
      {children}
    </div>
  )
}

interface StatCardProps {
  label: string
  value: number | string
  icon: ReactNode
  color?: 'violet' | 'indigo' | 'emerald' | 'rose' | 'amber' | 'sky'
  onClick?: () => void
}

export function StatCard({ label, value, icon, color = 'indigo', onClick }: StatCardProps) {
  const gradients: Record<string, string> = {
    violet: 'from-violet-500 to-purple-600',
    indigo: 'from-indigo-500 to-blue-600',
    emerald: 'from-emerald-500 to-teal-600',
    rose: 'from-rose-500 to-pink-600',
    amber: 'from-amber-500 to-orange-600',
    sky: 'from-sky-500 to-cyan-600',
  }

  const isClickable = !!onClick

  return (
    <Card
      className={`relative overflow-hidden ${isClickable ? 'cursor-pointer' : ''}`}
      hover={isClickable}
      onClick={onClick}
    >
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm font-medium text-slate-500 dark:text-slate-400">{label}</p>
          <p className="mt-2 text-3xl font-bold tracking-tight text-slate-900 dark:text-white">
            {value}
          </p>
        </div>
        <div
          className={`flex h-12 w-12 items-center justify-center rounded-xl bg-gradient-to-br ${gradients[color]} text-white shadow-lg`}
        >
          {icon}
        </div>
      </div>
    </Card>
  )
}

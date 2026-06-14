import type { ReactNode } from 'react'

interface FloatingActionButtonProps {
  icon: ReactNode
  label?: string
  onClick: () => void
  position?: 'bottom-right' | 'bottom-left'
  variant?: 'primary' | 'secondary'
  title?: string
}

export function FloatingActionButton({
  icon,
  label,
  onClick,
  position = 'bottom-right',
  variant = 'primary',
  title,
}: FloatingActionButtonProps) {
  const positionClass = position === 'bottom-right' ? 'right-6' : 'left-6'
  const variantClasses =
    variant === 'primary'
      ? 'bg-gradient-to-r from-violet-600 to-indigo-600 text-white shadow-lg shadow-indigo-500/25 hover:shadow-indigo-500/40 hover:from-violet-500 hover:to-indigo-500'
      : 'bg-white text-slate-700 shadow-lg border border-slate-200 hover:bg-slate-50 dark:bg-slate-800 dark:text-slate-200 dark:border-slate-700 dark:hover:bg-slate-750'

  return (
    <button
      type="button"
      onClick={onClick}
      title={title}
      className={`fixed bottom-6 ${positionClass} z-40 flex items-center gap-2 rounded-full px-4 py-3 font-medium transition-all duration-200 hover:-translate-y-0.5 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 focus:ring-offset-white dark:focus:ring-offset-slate-900 ${variantClasses}`}
    >
      {icon}
      {label && <span className="text-sm">{label}</span>}
    </button>
  )
}

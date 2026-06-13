import type { ReactNode } from 'react'
import { X } from 'lucide-react'
import { Button } from './Button'

interface ModalProps {
  title: string
  children: ReactNode
  onClose: () => void
  footer?: ReactNode
  size?: 'md' | 'lg' | 'xl'
}

export function Modal({ title, children, onClose, footer, size = 'md' }: ModalProps) {
  const widths = {
    md: 'max-w-lg',
    lg: 'max-w-2xl',
    xl: 'max-w-4xl',
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/60 backdrop-blur-sm"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose()
      }}
    >
      <div
        className={`w-full ${widths[size]} max-h-[90vh] overflow-y-auto rounded-2xl border border-slate-200/60 bg-white/95 backdrop-blur-xl shadow-2xl dark:border-slate-700/60 dark:bg-slate-900/95`}
      >
        <div className="flex items-center justify-between border-b border-slate-100 px-6 py-4 dark:border-slate-800">
          <h3 className="text-lg font-semibold text-slate-900 dark:text-white">{title}</h3>
          <Button variant="ghost" size="sm" onClick={onClose} aria-label="Close">
            <X className="h-4 w-4" />
          </Button>
        </div>
        <div className="px-6 py-5">{children}</div>
        {footer && (
          <div className="flex justify-end gap-2 border-t border-slate-100 px-6 py-4 dark:border-slate-800">
            {footer}
          </div>
        )}
      </div>
    </div>
  )
}

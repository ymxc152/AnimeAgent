import { useCallback, useState, useRef } from 'react'
import type { ReactNode } from 'react'
import { X } from 'lucide-react'
import { ToastContext } from './ToastContext'

interface Toast {
  id: string
  message: string
  type?: 'success' | 'error'
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])
  const timersRef = useRef<Record<string, number>>({})

  const removeToast = useCallback((id: string) => {
    if (timersRef.current[id]) {
      window.clearTimeout(timersRef.current[id])
      delete timersRef.current[id]
    }
    setToasts((prev) => prev.filter((t) => t.id !== id))
  }, [])

  const showToast = useCallback(
    (message: string, type: 'success' | 'error' = 'success') => {
      const id = `${Date.now()}-${Math.random()}`
      setToasts((prev) => [...prev, { id, message, type }])
      timersRef.current[id] = window.setTimeout(() => removeToast(id), 3000)
    },
    [removeToast]
  )

  return (
    <ToastContext.Provider value={{ showToast }}>
      {children}
      <div className="fixed bottom-4 right-4 z-[120] flex flex-col gap-2">
        {toasts.map((toast) => (
          <div
            key={toast.id}
            className={`flex items-center gap-3 rounded-xl px-4 py-3 text-sm font-medium shadow-lg backdrop-blur-xl transition-all ${
              toast.type === 'error'
                ? 'bg-rose-50 text-rose-700 dark:bg-rose-950/80 dark:text-rose-300'
                : 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/80 dark:text-emerald-300'
            }`}
            role="status"
          >
            {toast.message}
            <button
              onClick={() => removeToast(toast.id)}
              className="rounded p-0.5 hover:bg-black/5 dark:hover:bg-white/10"
              aria-label="Close"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}

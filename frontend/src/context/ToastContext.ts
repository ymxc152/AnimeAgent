import { createContext } from 'react'

export interface ToastContextValue {
  showToast: (message: string, type?: 'success' | 'error') => void
}

export const ToastContext = createContext<ToastContextValue | null>(null)

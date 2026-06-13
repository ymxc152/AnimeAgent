import { createContext } from 'react'
import type { Language } from './translations'

export interface I18nContextValue {
  language: Language
  setLanguage: (lang: Language) => void
  toggleLanguage: () => void
}

export const I18nContext = createContext<I18nContextValue | null>(null)

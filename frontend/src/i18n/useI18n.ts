import { useContext, useMemo } from 'react'
import { I18nContext } from './context'
import { translations } from './translations'

export function useI18n() {
  const ctx = useContext(I18nContext)
  if (!ctx) {
    throw new Error('useI18n must be used within I18nProvider')
  }
  const { language, setLanguage, toggleLanguage } = ctx
  const t = useMemo(() => translations[language], [language])

  return {
    language,
    setLanguage,
    toggleLanguage,
    t,
  }
}

export type { Language } from './translations'

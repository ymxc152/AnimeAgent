import { useCallback, useEffect, useState, type ReactNode } from 'react'
import type { Language } from './translations'
import { I18nContext } from './context'

export { I18nContext } from './context'

const STORAGE_KEY = 'animeagent-language'

function getInitialLanguage(): Language {
  if (typeof window === 'undefined') return 'zh-CN'
  const stored = window.localStorage.getItem(STORAGE_KEY) as Language | null
  if (stored === 'zh-CN' || stored === 'en') return stored
  const browserLang = navigator.language
  return browserLang.startsWith('zh') ? 'zh-CN' : 'en'
}

interface I18nProviderProps {
  children: ReactNode
}

export function I18nProvider({ children }: I18nProviderProps) {
  const [language, setLanguageState] = useState<Language>(getInitialLanguage)

  const setLanguage = useCallback((lang: Language) => {
    setLanguageState(lang)
    if (typeof window !== 'undefined') {
      window.localStorage.setItem(STORAGE_KEY, lang)
    }
  }, [])

  const toggleLanguage = useCallback(() => {
    setLanguage(language === 'zh-CN' ? 'en' : 'zh-CN')
  }, [language, setLanguage])

  useEffect(() => {
    document.documentElement.lang = language === 'zh-CN' ? 'zh-CN' : 'en'
  }, [language])

  return (
    <I18nContext.Provider value={{ language, setLanguage, toggleLanguage }}>
      {children}
    </I18nContext.Provider>
  )
}

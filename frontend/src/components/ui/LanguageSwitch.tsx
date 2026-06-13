import { useI18n } from '../../i18n/useI18n'

export function LanguageSwitch() {
  const { language, setLanguage, t } = useI18n()

  return (
    <div className="flex items-center gap-2 rounded-xl border border-slate-200 bg-slate-50 p-1 dark:border-slate-700 dark:bg-slate-800">
      {(['zh-CN', 'en'] as const).map((lang) => (
        <button
          key={lang}
          onClick={() => setLanguage(lang)}
          className={`
            rounded-lg px-3 py-1.5 text-sm font-medium transition-all duration-200
            ${
              language === lang
                ? 'bg-white text-indigo-600 shadow-sm dark:bg-slate-700 dark:text-indigo-300'
                : 'text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200'
            }
          `}
        >
          {lang === 'zh-CN' ? t.language.zh : t.language.en}
        </button>
      ))}
    </div>
  )
}

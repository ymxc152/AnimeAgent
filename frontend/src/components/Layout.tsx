import { useState } from 'react'
import { Link, NavLink, Outlet } from 'react-router-dom'
import {
  LayoutDashboard,
  ListVideo,
  PlayCircle,
  Compass,
  Rss,
  ScrollText,
  Sparkles,
  RefreshCw,
  MessageCircle,
} from 'lucide-react'
import { useI18n } from '../i18n/useI18n'
import { Button, LanguageSwitch } from './ui'

const navItems = [
  { path: '/', key: 'dashboard', icon: LayoutDashboard },
  { path: '/subscriptions', key: 'subscriptions', icon: ListVideo },
  { path: '/episodes', key: 'episodes', icon: PlayCircle },
  { path: '/discovery', key: 'discovery', icon: Compass },
  { path: '/rss-sources', key: 'rssSources', icon: Rss },
  { path: '/logs', key: 'logs', icon: ScrollText },
  { path: '/chat', key: 'chat', icon: MessageCircle },
] as const

export function Layout() {
  const { t } = useI18n()
  const [refreshKey, setRefreshKey] = useState(0)

  return (
    <div className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-50 border-b border-slate-200/60 bg-white/80 backdrop-blur-xl dark:border-slate-700/60 dark:bg-slate-900/80">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
          <Link to="/" className="flex items-center gap-2.5">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-violet-600 to-indigo-600 text-white shadow-lg shadow-indigo-500/25">
              <Sparkles className="h-5 w-5" />
            </div>
            <div className="flex flex-col">
              <span className="text-lg font-bold tracking-tight text-slate-900 dark:text-white">
                {t.app.name}
              </span>
              <span className="hidden text-[10px] font-medium text-slate-500 dark:text-slate-400 sm:block">
                {t.app.tagline}
              </span>
            </div>
          </Link>

          <nav className="hidden items-center gap-1 md:flex">
            {navItems.map((item) => {
              const Icon = item.icon
              return (
                <NavLink
                  key={item.path}
                  to={item.path}
                  end={item.path === '/'}
                  className={({ isActive }) =>
                    `group relative flex items-center gap-2 rounded-xl px-3.5 py-2 text-sm font-medium transition-all duration-200 ${
                      isActive
                        ? 'bg-indigo-50 text-indigo-600 dark:bg-indigo-500/10 dark:text-indigo-300'
                        : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900 dark:text-slate-400 dark:hover:bg-slate-800 dark:hover:text-white'
                    }`
                  }
                >
                  <Icon className="h-4 w-4" />
                  <span>{t.nav[item.key]}</span>
                </NavLink>
              )
            })}
          </nav>

          <div className="flex items-center gap-3">
            <Button
              variant="secondary"
              size="sm"
              onClick={() => setRefreshKey((k) => k + 1)}
              title={t.common.refresh || 'Refresh'}
              aria-label={t.common.refresh || 'Refresh'}
            >
              <RefreshCw className="h-4 w-4" />
            </Button>
            <LanguageSwitch />
          </div>
        </div>
      </header>

      <nav className="border-b border-slate-200/60 bg-white/60 backdrop-blur-lg dark:border-slate-700/60 dark:bg-slate-900/60 md:hidden">
        <div className="mx-auto flex max-w-7xl items-center gap-1 overflow-x-auto px-4 py-2 sm:px-6 lg:px-8">
          {navItems.map((item) => {
            const Icon = item.icon
            return (
              <NavLink
                key={item.path}
                to={item.path}
                end={item.path === '/'}
                className={({ isActive }) =>
                  `flex shrink-0 items-center gap-1.5 rounded-lg px-3 py-2 text-xs font-medium transition-colors ${
                    isActive
                      ? 'bg-indigo-50 text-indigo-600 dark:bg-indigo-500/10 dark:text-indigo-300'
                      : 'text-slate-600 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-800'
                  }`
                }
              >
                <Icon className="h-3.5 w-3.5" />
                <span>{t.nav[item.key]}</span>
              </NavLink>
            )
          })}
        </div>
      </nav>

      <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-8 sm:px-6 lg:px-8">
        <div className="animate-fade-in" key={refreshKey}>
          <Outlet />
        </div>
      </main>

      <footer className="border-t border-slate-200/60 bg-white/60 py-6 text-center text-xs text-slate-500 backdrop-blur-lg dark:border-slate-700/60 dark:bg-slate-900/60 dark:text-slate-500">
        <p>
          {t.app.name} · {t.app.tagline}
        </p>
      </footer>
    </div>
  )
}

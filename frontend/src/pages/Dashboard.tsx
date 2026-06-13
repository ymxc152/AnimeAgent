import { useEffect, useState } from 'react'
import { getStats, getToolsHealth } from '../api/client'
import type { Stats, ToolHealth } from '../types'
import { useI18n } from '../i18n/useI18n'
import { Card, StatCard, Badge, Loading, EmptyState } from '../components/ui'
import {
  ListVideo,
  PlayCircle,
  CheckCircle2,
  Clock,
  AlertTriangle,
  Activity,
  HeartPulse,
} from 'lucide-react'

export function Dashboard() {
  const { t } = useI18n()
  const [stats, setStats] = useState<Stats | null>(null)
  const [health, setHealth] = useState<Record<string, ToolHealth> | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const [statsData, healthData] = await Promise.all([getStats(), getToolsHealth()])
        if (!cancelled) {
          setStats(statsData)
          setHealth(healthData)
        }
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : 'Failed to load dashboard')
      }
    })()
    return () => { cancelled = true }
  }, [])

  if (error) {
    return (
      <EmptyState
        title={t.common.error}
        description={error}
        icon={<AlertTriangle className="h-8 w-8" />}
      />
    )
  }

  if (!stats || !health) {
    return <Loading message={t.common.loading} />
  }

  const healthEntries = Object.entries(health)
  const healthyCount = healthEntries.filter(([, s]) => s.healthy).length

  return (
    <div className="space-y-8">
      {/* Page header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-white">
          {t.dashboard.title}
        </h1>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          {t.app.tagline}
        </p>
      </div>

      {/* Subscription stats */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <StatCard
          label={t.dashboard.stats.total}
          value={stats.subscriptions.total}
          icon={<ListVideo className="h-6 w-6" />}
          color="indigo"
        />
        <StatCard
          label={t.dashboard.stats.ongoing}
          value={stats.subscriptions.ongoing}
          icon={<Clock className="h-6 w-6" />}
          color="amber"
        />
        <StatCard
          label={t.dashboard.stats.completed}
          value={stats.subscriptions.completed}
          icon={<CheckCircle2 className="h-6 w-6" />}
          color="emerald"
        />
      </div>

      {/* Episode stats */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <StatCard
          label={t.dashboard.stats.pending}
          value={stats.episodes.pending}
          icon={<PlayCircle className="h-6 w-6" />}
          color="sky"
        />
        <StatCard
          label={t.dashboard.stats.completed}
          value={stats.episodes.completed}
          icon={<CheckCircle2 className="h-6 w-6" />}
          color="emerald"
        />
        <StatCard
          label={t.dashboard.stats.failed}
          value={stats.episodes.failed}
          icon={<AlertTriangle className="h-6 w-6" />}
          color="rose"
        />
      </div>

      {/* Tool health */}
      <div>
        <div className="mb-4 flex items-center gap-2">
          <HeartPulse className="h-5 w-5 text-slate-500 dark:text-slate-400" />
          <h2 className="text-lg font-semibold text-slate-900 dark:text-white">
            {t.dashboard.toolHealth}
          </h2>
          <Badge variant={healthyCount === healthEntries.length ? 'success' : 'warning'}>
            {healthyCount}/{healthEntries.length}
          </Badge>
        </div>

        <Card padding="none">
          <div className="divide-y divide-slate-100 dark:divide-slate-800">
            {healthEntries.map(([name, status]) => (
              <div
                key={name}
                className="flex items-center justify-between px-5 py-3.5"
              >
                <div className="flex items-center gap-3">
                  <Activity className="h-4 w-4 text-slate-400" />
                  <span className="text-sm font-medium text-slate-700 dark:text-slate-300">
                    {name}
                  </span>
                </div>
                <Badge variant={status.healthy ? 'success' : 'danger'}>
                  {status.healthy ? t.dashboard.healthy : t.dashboard.unhealthy}
                </Badge>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  )
}

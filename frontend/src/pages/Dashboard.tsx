import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { getStats, getToolsHealth } from '../api/client'
import type { Stats, ToolHealth } from '../types'
import { useI18n } from '../i18n/useI18n'
import { usePolling } from '../hooks/usePolling'
import { Card, StatCard, Badge, Loading, EmptyState, Button } from '../components/ui'
import {
  ListVideo,
  PlayCircle,
  CheckCircle2,
  Clock,
  AlertTriangle,
  Activity,
  HeartPulse,
  RefreshCw,
} from 'lucide-react'

const POLL_INTERVAL = 5000

export function Dashboard() {
  const { t } = useI18n()
  const navigate = useNavigate()
  const [stats, setStats] = useState<Stats | null>(null)
  const [health, setHealth] = useState<Record<string, ToolHealth> | null>(null)
  const [healthLoading, setHealthLoading] = useState(false)
  const [lastChecked, setLastChecked] = useState<Date | null>(null)
  const [error, setError] = useState<string | null>(null)

  const loadStats = useCallback(async () => {
    try {
      const statsData = await getStats()
      setStats(statsData)
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load stats')
    }
  }, [])

  const loadHealth = useCallback(async () => {
    setHealthLoading(true)
    try {
      const healthData = await getToolsHealth()
      setHealth(healthData)
      setLastChecked(new Date())
    } finally {
      setHealthLoading(false)
    }
  }, [])

  useEffect(() => {
    void (async () => {
      await loadStats()
      await loadHealth()
    })()
  }, [loadStats, loadHealth])

  usePolling(loadStats, POLL_INTERVAL)

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
          onClick={() => navigate('/subscriptions')}
        />
        <StatCard
          label={t.dashboard.stats.ongoing}
          value={stats.subscriptions.ongoing}
          icon={<Clock className="h-6 w-6" />}
          color="amber"
          onClick={() => navigate('/subscriptions')}
        />
        <StatCard
          label={t.dashboard.stats.completed}
          value={stats.subscriptions.completed}
          icon={<CheckCircle2 className="h-6 w-6" />}
          color="emerald"
          onClick={() => navigate('/subscriptions')}
        />
      </div>

      {/* Episode stats */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <StatCard
          label={t.dashboard.stats.pending}
          value={stats.episodes.pending}
          icon={<PlayCircle className="h-6 w-6" />}
          color="sky"
          onClick={() => navigate('/episodes')}
        />
        <StatCard
          label={t.dashboard.stats.completed}
          value={stats.episodes.completed}
          icon={<CheckCircle2 className="h-6 w-6" />}
          color="emerald"
          onClick={() => navigate('/episodes')}
        />
        <StatCard
          label={t.dashboard.stats.failed}
          value={stats.episodes.failed}
          icon={<AlertTriangle className="h-6 w-6" />}
          color="rose"
          onClick={() => navigate('/episodes?status=failed')}
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
          <Button
            variant="secondary"
            size="sm"
            isLoading={healthLoading}
            onClick={loadHealth}
            className="ml-auto"
          >
            <RefreshCw className="h-3.5 w-3.5" />
            {t.dashboard.refreshHealth}
          </Button>
        </div>
        {lastChecked && (
          <p className="mb-3 text-xs text-slate-500 dark:text-slate-400">
            {t.dashboard.lastChecked}: {lastChecked.toLocaleTimeString()}
          </p>
        )}

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

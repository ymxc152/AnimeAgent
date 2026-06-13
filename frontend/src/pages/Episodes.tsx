import { useCallback, useEffect, useState } from 'react'
import { listEpisodes, listSubscriptions, retryEpisode, submitHumanInput } from '../api/client'
import type { Episode, Subscription } from '../types'
import { useI18n } from '../i18n/useI18n'
import { Card, Button, Input, Select, Badge, Loading, EmptyState } from '../components/ui'
import { PlayCircle, RefreshCw, CheckCircle2, XCircle, AlertTriangle } from 'lucide-react'

const STATUS_BADGE_VARIANT: Record<string, 'success' | 'danger' | 'warning' | 'info' | 'primary' | 'muted'> = {
  pending: 'muted',
  fetching: 'info',
  matched: 'primary',
  downloading: 'info',
  downloaded: 'primary',
  organized: 'primary',
  organized_with_warnings: 'warning',
  completed: 'success',
  failed: 'danger',
  human_review: 'warning',
  waiting_for_rss: 'muted',
  no_match: 'danger',
  low_confidence: 'warning',
}

export function Episodes() {
  const { t } = useI18n()
  const [episodes, setEpisodes] = useState<Episode[]>([])
  const [subscriptions, setSubscriptions] = useState<Subscription[]>([])
  const [subscriptionId, setSubscriptionId] = useState<string>('')
  const [statusFilter, setStatusFilter] = useState<string>('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [humanInput, setHumanInput] = useState<Record<number, string>>({})

   
  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [epsData, subsData] = await Promise.all([
        listEpisodes(
          subscriptionId ? Number(subscriptionId) : undefined,
          statusFilter || undefined
        ),
        listSubscriptions(),
      ])
      setEpisodes(epsData)
      setSubscriptions(subsData)
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load')
    } finally {
      setLoading(false)
    }
  }, [subscriptionId, statusFilter])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- initial data load
  useEffect(() => { void load() }, [load])

  async function handleRetry(id: number) {
    try {
      await retryEpisode(id)
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : t.common.error)
    }
  }

  async function handleHumanAction(id: number, action: 'approve' | 'reject') {
    try {
      await submitHumanInput(id, {
        action,
        torrent_link: humanInput[id] || null,
      })
      setHumanInput((prev) => ({ ...prev, [id]: '' }))
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : t.common.error)
    }
  }

  const subOptions = [
    { value: '', label: t.episodes.filters.allSubscriptions },
    ...subscriptions.map((s) => ({
      value: String(s.id),
      label: s.title_chinese || s.title_romaji,
    })),
  ]

  const statusOptions = [
    { value: '', label: t.episodes.filters.allStatuses },
    { value: 'pending', label: t.episodes.statuses.pending },
    { value: 'fetching', label: t.episodes.statuses.fetching },
    { value: 'matched', label: t.episodes.statuses.matched },
    { value: 'downloading', label: t.episodes.statuses.downloading },
    { value: 'completed', label: t.episodes.statuses.completed },
    { value: 'failed', label: t.episodes.statuses.failed },
    { value: 'human_review', label: t.episodes.statuses.human_review },
  ]

  return (
    <div className="space-y-8">
      {/* Page header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-white">
          {t.episodes.title}
        </h1>
      </div>

      {/* Error banner */}
      {error && (
        <Card className="border-rose-200 bg-rose-50 dark:border-rose-800 dark:bg-rose-950/30">
          <p className="text-sm text-rose-600 dark:text-rose-400">{error}</p>
        </Card>
      )}

      {/* Filters */}
      <Card>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Select
            label={t.episodes.filters.subscription}
            options={subOptions}
            value={subscriptionId}
            onChange={(e) => setSubscriptionId(e.target.value)}
          />
          <Select
            label={t.episodes.filters.status}
            options={statusOptions}
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
          />
        </div>
      </Card>

      {/* Episode list */}
      {loading ? (
        <Loading message={t.common.loading} />
      ) : episodes.length === 0 ? (
        <EmptyState
          title={t.episodes.noEpisodes}
          icon={<PlayCircle className="h-8 w-8" />}
        />
      ) : (
        <div className="space-y-3">
          {episodes.map((ep) => (
            <Card key={ep.id} hover>
              <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                <div className="min-w-0 flex-1 space-y-2">
                  {ep.subscription_title && (
                    <p className="text-sm font-medium text-indigo-600 dark:text-indigo-400">
                      {ep.subscription_title}
                    </p>
                  )}
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-base font-semibold text-slate-900 dark:text-white">
                      {t.episodes.episodeNumber.replace('{number}', String(ep.episode_number))}
                    </span>
                    <Badge variant={STATUS_BADGE_VARIANT[ep.status] || 'muted'}>
                      {t.episodes.statuses[ep.status as keyof typeof t.episodes.statuses] || ep.status}
                    </Badge>
                  </div>
                  <p className="text-xs text-slate-400 dark:text-slate-500">
                    {t.episodes.statusHelp[ep.status as keyof typeof t.episodes.statusHelp] || ''}
                  </p>
                  {ep.torrent_title && (
                    <p className="truncate text-sm text-slate-500 dark:text-slate-400">
                      {ep.torrent_title}
                    </p>
                  )}
                  {ep.error_log && (
                    <div className="flex items-start gap-2 rounded-lg bg-rose-50 px-3 py-2 dark:bg-rose-950/20">
                      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-rose-500" />
                      <p className="text-sm text-rose-600 dark:text-rose-400">{ep.error_log}</p>
                    </div>
                  )}
                </div>

                <div className="flex shrink-0 items-center gap-2">
                  {ep.status === 'failed' && (
                    <Button variant="secondary" size="sm" onClick={() => handleRetry(ep.id)}>
                      <RefreshCw className="h-3.5 w-3.5" />
                      {t.episodes.retry}
                    </Button>
                  )}
                  {ep.status === 'human_review' && (
                    <div className="flex items-center gap-2">
                      <Input
                        placeholder={t.episodes.humanReview.placeholder}
                        value={humanInput[ep.id] || ''}
                        onChange={(e) =>
                          setHumanInput((prev) => ({ ...prev, [ep.id]: e.target.value }))
                        }
                        className="!w-64"
                      />
                      <Button
                        variant="primary"
                        size="sm"
                        onClick={() => handleHumanAction(ep.id, 'approve')}
                      >
                        <CheckCircle2 className="h-3.5 w-3.5" />
                        {t.episodes.humanReview.approve}
                      </Button>
                      <Button
                        variant="danger"
                        size="sm"
                        onClick={() => handleHumanAction(ep.id, 'reject')}
                      >
                        <XCircle className="h-3.5 w-3.5" />
                        {t.episodes.humanReview.reject}
                      </Button>
                    </div>
                  )}
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}

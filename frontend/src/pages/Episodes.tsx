import { useCallback, useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import {
  getEpisodeDetail,
  listEpisodes,
  listSubscriptions,
  retryEpisode,
  submitHumanInput,
} from '../api/client'
import type { Episode, EpisodeDetail, Subscription } from '../types'
import { useI18n } from '../i18n/useI18n'
import { usePolling } from '../hooks/usePolling'
import {
  Card,
  Button,
  Input,
  Select,
  Badge,
  Loading,
  EmptyState,
  Modal,
  MultiSelect,
} from '../components/ui'
import {
  PlayCircle,
  RefreshCw,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Info,
  Download,
} from 'lucide-react'

const POLL_INTERVAL = 5000

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

function formatSpeed(kbps: number): string {
  if (kbps <= 0) return ''
  if (kbps < 1024) return `${kbps.toFixed(1)} KB/s`
  return `${(kbps / 1024).toFixed(2)} MB/s`
}

function formatProgress(progress: number): string {
  const pct = Math.round((progress || 0) * 100)
  return `${pct}%`
}

export function Episodes() {
  const { t } = useI18n()
  const [searchParams, setSearchParams] = useSearchParams()
  const [episodes, setEpisodes] = useState<Episode[]>([])
  const [subscriptions, setSubscriptions] = useState<Subscription[]>([])
  const [subscriptionId, setSubscriptionId] = useState<string>(() => searchParams.get('subscription_id') || '')
  const [statusFilter, setStatusFilter] = useState<string[]>(() => {
    const status = searchParams.get('status')
    return status ? status.split(',') : []
  })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [humanInput, setHumanInput] = useState<Record<number, string>>({})
  const [detailId, setDetailId] = useState<number | null>(null)
  const [detail, setDetail] = useState<EpisodeDetail | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [epsData, subsData] = await Promise.all([
        listEpisodes(
          subscriptionId ? Number(subscriptionId) : undefined,
          statusFilter.length > 0 ? statusFilter : undefined
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

  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { void load() }, [load])
  usePolling(load, POLL_INTERVAL)

  // Sync filters with URL query params
  useEffect(() => {
    const params = new URLSearchParams()
    if (subscriptionId) params.set('subscription_id', subscriptionId)
    if (statusFilter.length > 0) params.set('status', statusFilter.join(','))
    setSearchParams(params, { replace: true })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [subscriptionId, statusFilter])

  useEffect(() => {
    if (detailId === null) return
    getEpisodeDetail(detailId)
      .then(setDetail)
      .catch((err) => setError(err instanceof Error ? err.message : t.common.error))
      .finally(() => setDetailLoading(false))
  }, [detailId, t.common.error])

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

  const statusOptions = useMemo(
    () => [
      { value: 'pending', label: t.episodes.statuses.pending },
      { value: 'fetching', label: t.episodes.statuses.fetching },
      { value: 'matched', label: t.episodes.statuses.matched },
      { value: 'downloading', label: t.episodes.statuses.downloading },
      { value: 'completed', label: t.episodes.statuses.completed },
      { value: 'failed', label: t.episodes.statuses.failed },
      { value: 'human_review', label: t.episodes.statuses.human_review },
      { value: 'waiting_for_rss', label: t.episodes.statuses.waiting_for_rss },
    ],
    [t.episodes.statuses]
  )

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
      <Card padding="sm">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Select
            label={t.episodes.filters.subscription}
            options={subOptions}
            value={subscriptionId}
            onChange={(e) => setSubscriptionId(e.target.value)}
          />
          <MultiSelect
            label={t.episodes.filters.status}
            options={statusOptions}
            value={statusFilter}
            onChange={setStatusFilter}
            placeholder={t.episodes.filters.allStatuses}
          />
        </div>
      </Card>

      {/* Episode list */}
      {loading && episodes.length === 0 ? (
        <Loading message={t.common.loading} />
      ) : episodes.length === 0 ? (
        <Card padding="lg">
          <EmptyState
            title={t.episodes.noEpisodes}
            icon={<PlayCircle className="h-8 w-8" />}
          />
        </Card>
      ) : (
        <div className="space-y-3">
          {episodes.map((ep) => (
            <Card
              key={ep.id}
              hover
              onClick={() => { setDetailId(ep.id); setDetailLoading(true) }}
              className="cursor-pointer"
            >
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

                  {ep.status === 'downloading' && (
                    <div className="space-y-1">
                      <div className="flex items-center justify-between text-xs text-slate-500 dark:text-slate-400">
                        <span className="flex items-center gap-1">
                          <Download className="h-3 w-3" />
                          {formatSpeed(ep.torrent_last_speed)}
                        </span>
                        <span>{formatProgress(ep.torrent_progress)}</span>
                      </div>
                      <div className="h-2 w-full overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800">
                        <div
                          className="h-full rounded-full bg-gradient-to-r from-sky-500 to-cyan-500 transition-all duration-500"
                          style={{ width: formatProgress(ep.torrent_progress) }}
                        />
                      </div>
                    </div>
                  )}

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

                <div
                  className="flex shrink-0 items-center gap-2"
                  onClick={(e) => e.stopPropagation()}
                >
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

      {/* Detail modal */}
      {detailId !== null && (
        <Modal
          title={
            detail
              ? t.episodes.detail.title
                  .replace('{title}', detail.subscription_title || t.discovery.unknown)
                  .replace('{number}', String(detail.episode_number))
              : t.episodes.title
          }
          onClose={() => setDetailId(null)}
          size="xl"
        >
          {detailLoading || !detail ? (
            <Loading message={t.common.loading} />
          ) : (
            <div className="space-y-5">
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant={STATUS_BADGE_VARIANT[detail.status] || 'muted'}>
                  {t.episodes.statuses[detail.status as keyof typeof t.episodes.statuses] || detail.status}
                </Badge>
                {detail.content_type && (
                  <Badge variant="muted">{detail.content_type}</Badge>
                )}
              </div>

              <DetailSection title={t.episodes.detail.torrentInfo} icon={<Download className="h-4 w-4" />}>
                <DetailRow label={t.episodes.torrentTitle} value={detail.torrent_title} />
                <DetailRow label={t.episodes.detail.torrentName} value={detail.torrent_name} />
                <DetailRow label={t.episodes.detail.infoHash} value={detail.torrent_hash} />
                <DetailRow label={t.episodes.detail.qbStatus} value={detail.torrent_status} />
                <DetailRow label={t.episodes.detail.progress} value={formatProgress(detail.torrent_progress)} />
                <DetailRow label={t.episodes.detail.downloadSpeed} value={formatSpeed(detail.torrent_last_speed)} />
                <DetailRow label={t.episodes.detail.candidateCount} value={String(detail.torrent_candidates_count)} />
              </DetailSection>

              <DetailSection title={t.episodes.detail.paths} icon={<Info className="h-4 w-4" />}>
                <DetailRow label={t.episodes.detail.downloadPath} value={detail.download_path} />
                <DetailRow label={t.episodes.detail.organizedPath} value={detail.organized_path} />
              </DetailSection>

              {detail.torrent_failed_hashes.length > 0 && (
                <DetailSection title={t.episodes.detail.failedHashes} icon={<AlertTriangle className="h-4 w-4" />}>
                  <ul className="list-inside list-disc space-y-1 text-sm text-slate-600 dark:text-slate-400">
                    {detail.torrent_failed_hashes.map((h) => (
                      <li key={h} className="break-all">{h}</li>
                    ))}
                  </ul>
                </DetailSection>
              )}

              {detail.error_log && (
                <DetailSection title={t.episodes.errorLog} icon={<AlertTriangle className="h-4 w-4 text-rose-500" />}>
                  <p className="whitespace-pre-wrap rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-600 dark:bg-rose-950/20 dark:text-rose-400">
                    {detail.error_log}
                  </p>
                </DetailSection>
              )}

              {detail.torrent_candidates.length > 0 && (
                <DetailSection title={t.episodes.detail.candidates} icon={<Info className="h-4 w-4" />}>
                  <div className="max-h-48 overflow-y-auto space-y-2">
                    {detail.torrent_candidates.slice(0, 20).map((c, idx) => (
                      <div
                        key={idx}
                        className="rounded-lg border border-slate-100 p-2 text-sm dark:border-slate-800"
                      >
                        <p className="font-medium text-slate-800 dark:text-slate-200">
                          {(c as { title?: string }).title || 'Unknown'}
                        </p>
                        <p className="text-xs text-slate-500 dark:text-slate-400 break-all">
                          {(c as { info_hash?: string }).info_hash || 'no hash'}
                        </p>
                      </div>
                    ))}
                  </div>
                </DetailSection>
              )}
            </div>
          )}
        </Modal>
      )}


    </div>
  )
}

function DetailSection({ title, icon, children }: { title: string; icon: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="space-y-2">
      <h4 className="flex items-center gap-2 text-sm font-semibold text-slate-800 dark:text-slate-200">
        {icon}
        {title}
      </h4>
      <div className="pl-6">{children}</div>
    </div>
  )
}

function DetailRow({ label, value }: { label: string; value: string | null }) {
  return (
    <div className="grid grid-cols-3 gap-2 text-sm">
      <span className="text-slate-500 dark:text-slate-400">{label}</span>
      <span className="col-span-2 break-all text-slate-800 dark:text-slate-200">
        {value || '-'}
      </span>
    </div>
  )
}

import { useCallback, useEffect, useState } from 'react'
import {
  createSubscription,
  deleteSubscription,
  listSubscriptions,
  lookupAnime,
  refreshSubscriptionMetadata,
  searchAnime,
  updateSubscription,
} from '../api/client'
import type { AnimeLookup, Subscription, SubscriptionCreateRequest } from '../types'
import { useI18n } from '../i18n/useI18n'
import { usePolling } from '../hooks/usePolling'
import { useToast } from '../hooks/useToast'
import { AnimeCandidateDialog } from '../components/AnimeCandidateDialog'
import { Card, Button, Input, Switch, Badge, Loading, EmptyState, Modal } from '../components/ui'
import { Plus, Trash2, ListVideo, RefreshCw, Search } from 'lucide-react'

const POLL_INTERVAL = 5000

const SUBSCRIPTION_STATUS_VARIANT: Record<string, 'primary' | 'success' | 'muted'> = {
  ongoing: 'primary',
  completed: 'success',
  dropped: 'muted',
}

const EMPTY_FORM: SubscriptionCreateRequest = {
  title_romaji: '',
  title_chinese: '',
  title_native: '',
  total_episodes: undefined,
  auto_download_enabled: true,
  bangumi_id: null,
  anilist_id: null,
  tmdb_id: null,
}

export function Subscriptions() {
  const { t } = useI18n()
  const { showToast } = useToast()
  const [subscriptions, setSubscriptions] = useState<Subscription[]>([])
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState<Set<number>>(new Set())
  const [error, setError] = useState<string | null>(null)
  const [showModal, setShowModal] = useState(false)
  const [form, setForm] = useState<SubscriptionCreateRequest>(EMPTY_FORM)
  const [formError, setFormError] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [showCandidateDialog, setShowCandidateDialog] = useState(false)
  const [candidates, setCandidates] = useState<AnimeLookup[]>([])
  const [candidateLoading, setCandidateLoading] = useState(false)
  const [candidateError, setCandidateError] = useState<string | null>(null)
  const [totalEditable, setTotalEditable] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const subsData = await listSubscriptions()
      setSubscriptions(subsData)
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load')
    } finally {
      setLoading(false)
    }
  }, [])

  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { void load() }, [load])
  // 打开弹窗时暂停自动刷新，避免打断手动输入 / 选择候选
  usePolling(load, POLL_INTERVAL, !showModal && !showCandidateDialog)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setFormError(null)
    try {
      await createSubscription(form)
      setForm(EMPTY_FORM)
      setSearchQuery('')
      setShowModal(false)
      setTotalEditable(false)
      await load()
      showToast(t.subscriptions.lookupSuccess)
    } catch (err) {
      setFormError(err instanceof Error ? err.message : t.subscriptions.createError)
    }
  }

  function fillFormFromLookup(anime: AnimeLookup) {
    setForm((prev) => ({
      ...prev,
      bangumi_id: anime.bangumi_id ?? prev.bangumi_id,
      anilist_id: anime.anilist_id ?? prev.anilist_id,
      tmdb_id: anime.tmdb_id ?? prev.tmdb_id,
      title_romaji: anime.title_romaji || prev.title_romaji,
      title_native: anime.title_native || prev.title_native,
      title_chinese: anime.title_chinese || prev.title_chinese,
      total_episodes: anime.total_episodes ?? prev.total_episodes,
    }))
    if (anime.total_episodes) {
      setTotalEditable(false)
    }
  }

  function candidateKey(candidate: AnimeLookup) {
    return `${candidate.bangumi_id ?? ''}-${candidate.anilist_id ?? ''}-${candidate.tmdb_id ?? ''}`
  }

  async function handleSearch() {
    const query = searchQuery.trim()
    const idEntries: { source: 'bangumi' | 'anilist' | 'tmdb'; id: number }[] = [
      { source: 'bangumi', id: form.bangumi_id },
      { source: 'anilist', id: form.anilist_id },
      { source: 'tmdb', id: form.tmdb_id },
    ].filter((entry): entry is { source: 'bangumi' | 'anilist' | 'tmdb'; id: number } =>
      typeof entry.id === 'number' && entry.id > 0
    )

    if (!query && idEntries.length === 0) {
      setFormError(t.subscriptions.searchNeedInput || '请输入标题或至少填写一个外部 ID')
      return
    }

    setFormError(null)
    setCandidateLoading(true)
    setCandidateError(null)
    setCandidates([])
    setShowCandidateDialog(true)

    try {
      if (query) {
        const { candidates } = await searchAnime(query)
        setCandidates(candidates)
        if (candidates.length === 0) {
          setCandidateError(t.subscriptions.noResults)
        }
      } else {
        const results: AnimeLookup[] = []
        const errors: string[] = []
        for (const { source, id } of idEntries) {
          try {
            const anime = await lookupAnime(source, id)
            results.push(anime)
          } catch (err) {
            errors.push(err instanceof Error ? err.message : t.common.error)
          }
        }
        const deduped = results.filter(
          (item, index, arr) => arr.findIndex((c) => candidateKey(c) === candidateKey(item)) === index
        )
        setCandidates(deduped)
        if (deduped.length === 0) {
          setCandidateError(errors[0] || t.subscriptions.noResults)
        }
      }
    } catch (err) {
      setCandidateError(err instanceof Error ? err.message : t.common.error)
    } finally {
      setCandidateLoading(false)
    }
  }

  function handleSelect(candidate: AnimeLookup) {
    fillFormFromLookup(candidate)
    setSearchQuery('')
    showToast(t.subscriptions.lookupSuccess)
  }

  async function toggleAutoDownload(sub: Subscription) {
    try {
      await updateSubscription(sub.id, { auto_download_enabled: !sub.auto_download_enabled })
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : t.subscriptions.toggleError)
    }
  }

  async function handleDelete(id: number) {
    if (!confirm(t.subscriptions.deleteConfirm)) return
    try {
      await deleteSubscription(id)
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : t.subscriptions.deleteError)
    }
  }

  async function handleRefresh(id: number) {
    setRefreshing((prev) => new Set(prev).add(id))
    try {
      await refreshSubscriptionMetadata(id)
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : t.common.error)
    } finally {
      setRefreshing((prev) => {
        const next = new Set(prev)
        next.delete(id)
        return next
      })
    }
  }

  if (loading) return <Loading message={t.common.loading} />

  const canSearch =
    searchQuery.trim().length > 0 || Boolean(form.bangumi_id) || Boolean(form.anilist_id) || Boolean(form.tmdb_id)

  return (
    <div className="space-y-8">
      {/* Page header */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-white">
          {t.subscriptions.title}
        </h1>
        <Button variant="primary" onClick={() => setShowModal(true)}>
          <Plus className="h-4 w-4" />
          {t.subscriptions.addSubscription}
        </Button>
      </div>

      {/* Error banner */}
      {error && (
        <Card className="border-rose-200 bg-rose-50 dark:border-rose-800 dark:bg-rose-950/30">
          <p className="text-sm text-rose-600 dark:text-rose-400">{error}</p>
        </Card>
      )}

      {/* Subscription list */}
      {subscriptions.length === 0 ? (
        <Card padding="lg">
          <EmptyState
            title={t.subscriptions.noSubscriptions}
            icon={<ListVideo className="h-8 w-8" />}
          />
        </Card>
      ) : (
        <div className="space-y-3">
          {subscriptions.map((sub) => {
            const total = sub.ep_total || sub.total_episodes || 0
            const downloaded = sub.ep_downloaded
            const failed = sub.ep_failed
            const pending = sub.ep_pending
            const progressPct = total > 0 ? Math.round((downloaded / total) * 100) : 0

            return (
              <Card key={sub.id} hover>
                <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <h3 className="truncate text-base font-semibold text-slate-900 dark:text-white">
                        {sub.title_chinese || sub.title_native || sub.title_romaji}
                      </h3>
                      <Badge variant={SUBSCRIPTION_STATUS_VARIANT[sub.status] || 'muted'}>
                        {t.subscriptions.statuses[sub.status as keyof typeof t.subscriptions.statuses] || sub.status}
                      </Badge>
                    </div>
                    {(sub.title_native || sub.title_romaji) && (sub.title_chinese || sub.title_native) && (
                      <p className="mt-0.5 truncate text-sm text-slate-500 dark:text-slate-400">
                        {sub.title_native || sub.title_romaji}
                      </p>
                    )}
                    {/* Episode progress */}
                    <div className="mt-3 flex items-center gap-3">
                      <div className="flex-1">
                        <div className="flex items-center justify-between text-xs text-slate-500 dark:text-slate-400 mb-1">
                          <span>{t.subscriptions.progress}</span>
                          <span>{t.subscriptions.episodeProgress.replace('{downloaded}', String(downloaded)).replace('{total}', String(total))}</span>
                        </div>
                        <div className="h-2 w-full overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800">
                          <div
                            className="h-full rounded-full bg-gradient-to-r from-indigo-500 to-violet-500 transition-all duration-500"
                            style={{ width: `${progressPct}%` }}
                          />
                        </div>
                      </div>
                      <div className="flex shrink-0 items-center gap-2">
                        {failed > 0 && (
                          <Badge variant="danger" size="sm">
                            {t.subscriptions.failed} {failed}
                          </Badge>
                        )}
                        {pending > 0 && (
                          <Badge variant="muted" size="sm">
                            {t.subscriptions.pending} {pending}
                          </Badge>
                        )}
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-4">
                    <Switch
                      checked={sub.auto_download_enabled}
                      onChange={() => toggleAutoDownload(sub)}
                      label={t.subscriptions.form.autoDownload}
                    />
                    {!sub.title_chinese && (
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => handleRefresh(sub.id)}
                        isLoading={refreshing.has(sub.id)}
                      >
                        <RefreshCw className="h-3.5 w-3.5" />
                        {t.subscriptions.refreshMetadata}
                      </Button>
                    )}
                    <Button
                      variant="danger"
                      size="sm"
                      onClick={() => handleDelete(sub.id)}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                      {t.common.delete}
                    </Button>
                  </div>
                </div>
              </Card>
            )
          })}
        </div>
      )}


      {/* Add subscription modal */}
      {showModal && (
        <Modal
          title={t.subscriptions.addSubscription}
          onClose={() => setShowModal(false)}
          size="lg"
          footer={
            <>
              <Button variant="secondary" onClick={() => setShowModal(false)}>
                {t.common.cancel}
              </Button>
              <Button variant="primary" onClick={handleSubmit}>
                {t.common.add}
              </Button>
            </>
          }
        >
          <form onSubmit={handleSubmit} className="grid grid-cols-1 gap-4">
            {formError && (
              <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-600 dark:border-rose-800 dark:bg-rose-950/30 dark:text-rose-400">
                {formError}
              </div>
            )}

            <div className="space-y-3 rounded-xl border border-slate-100 bg-slate-50/50 p-4 dark:border-slate-800 dark:bg-slate-800/30">
              <p className="text-xs font-medium text-slate-500 dark:text-slate-400">
                {t.subscriptions.searchByTitleOrId || '通过标题或外部 ID 搜索'}
              </p>
              <Input
                placeholder={t.subscriptions.titlePlaceholder}
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    e.preventDefault()
                    void handleSearch()
                  }
                }}
              />
              <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
                <Input
                  type="number"
                  placeholder="Bangumi ID"
                  value={form.bangumi_id ?? ''}
                  onChange={(e) => setForm({ ...form, bangumi_id: e.target.value ? Number(e.target.value) : null })}
                />
                <Input
                  type="number"
                  placeholder="AniList ID"
                  value={form.anilist_id ?? ''}
                  onChange={(e) => setForm({ ...form, anilist_id: e.target.value ? Number(e.target.value) : null })}
                />
                <Input
                  type="number"
                  placeholder={t.subscriptions.tmdbId}
                  value={form.tmdb_id ?? ''}
                  onChange={(e) => setForm({ ...form, tmdb_id: e.target.value ? Number(e.target.value) : null })}
                />
              </div>
              <Button
                type="button"
                variant="primary"
                onClick={() => void handleSearch()}
                isLoading={candidateLoading}
                disabled={!canSearch}
              >
                <Search className="h-4 w-4" />
                {t.common.search}
              </Button>
            </div>

            <Input
              placeholder={t.subscriptions.form.chineseTitle}
              value={form.title_chinese || ''}
              onChange={(e) => setForm({ ...form, title_chinese: e.target.value })}
            />
            <Input
              placeholder={t.subscriptions.form.nativeTitle}
              value={form.title_native || ''}
              onChange={(e) => setForm({ ...form, title_native: e.target.value })}
            />
            <Input
              placeholder={t.subscriptions.form.romajiTitle}
              value={form.title_romaji}
              onChange={(e) => setForm({ ...form, title_romaji: e.target.value })}
              required
            />

            <div className="flex items-end gap-2">
              <Input
                type="number"
                placeholder={t.subscriptions.form.totalEpisodes}
                value={form.total_episodes ?? ''}
                onChange={(e) => setForm({ ...form, total_episodes: e.target.value ? Number(e.target.value) : undefined })}
                disabled={!totalEditable}
                className="flex-1"
              />
              <Button
                type="button"
                variant="secondary"
                size="sm"
                onClick={() => setTotalEditable((v) => !v)}
              >
                {totalEditable ? t.common.lock : t.common.edit}
              </Button>
            </div>

            <div className="flex items-center justify-between rounded-xl border border-slate-100 bg-slate-50/50 p-3 dark:border-slate-800 dark:bg-slate-800/30">
              <span className="text-sm text-slate-700 dark:text-slate-300">
                {t.subscriptions.form.autoDownload}
              </span>
              <Switch
                checked={form.auto_download_enabled ?? true}
                onChange={(checked) => setForm({ ...form, auto_download_enabled: checked })}
              />
            </div>
          </form>
        </Modal>
      )}

      <AnimeCandidateDialog
        open={showCandidateDialog}
        title={t.subscriptions.selectCandidateTitle}
        candidates={candidates}
        loading={candidateLoading}
        error={candidateError}
        onClose={() => setShowCandidateDialog(false)}
        onSelect={handleSelect}
      />
    </div>
  )
}

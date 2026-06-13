import { useEffect, useState } from 'react'
import { discoverySeason, discoverySubscribe, listSubscriptions } from '../api/client'
import type { DiscoveryAnime, Subscription, SubscriptionCreateRequest } from '../types'
import { useI18n } from '../i18n/useI18n'
import { Card, Button, Input, Select, Badge, Loading, EmptyState } from '../components/ui'
import { Compass, Search, Plus, Filter, X } from 'lucide-react'

const SEASONS = ['WINTER', 'SPRING', 'SUMMER', 'FALL']
const CACHE_KEY = 'animeagent-discovery-cache'

interface CacheData {
  year: number
  season: string
  results: DiscoveryAnime[]
  timestamp: number
}

function loadCache(): CacheData | null {
  try {
    const raw = sessionStorage.getItem(CACHE_KEY)
    if (!raw) return null
    return JSON.parse(raw)
  } catch {
    return null
  }
}

function saveCache(data: CacheData) {
  try {
    sessionStorage.setItem(CACHE_KEY, JSON.stringify(data))
  } catch {
    // ignore
  }
}

const DEFAULT_YEAR = new Date().getFullYear()
const DEFAULT_SEASON = SEASONS[Math.floor((new Date().getMonth() + 1) / 3) % 4]

function getCachedYear(): number {
  return loadCache()?.year ?? DEFAULT_YEAR
}
function getCachedSeason(): string {
  return loadCache()?.season ?? DEFAULT_SEASON
}
function getCachedResults(): DiscoveryAnime[] {
  return loadCache()?.results ?? []
}

export function Discovery() {
  const { t } = useI18n()
  const [year, setYear] = useState<number>(getCachedYear)
  const [season, setSeason] = useState<string>(getCachedSeason)
  const [results, setResults] = useState<DiscoveryAnime[]>(getCachedResults)
  const [subscriptions, setSubscriptions] = useState<Subscription[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [subscribing, setSubscribing] = useState<Set<number>>(new Set())

  // Filters
  const [searchQuery, setSearchQuery] = useState('')
  const [typeFilter, setTypeFilter] = useState('')

  // Load subscriptions; auto-load if no cache
  useEffect(() => {
    listSubscriptions().then(setSubscriptions).catch(() => {})

    if (results.length === 0) {
      // No cache — fetch current season
      void (async () => {
        setLoading(true)
        try {
          const data = await discoverySeason(year, season)
          setResults(data)
          saveCache({ year, season, results: data, timestamp: Date.now() })
        } catch {
          // silent
        } finally {
          setLoading(false)
        }
      })()
    }
  }, [])

  async function handleSearch(y?: number, s?: string) {
    const searchYear = y ?? year
    const searchSeason = s ?? season
    setLoading(true)
    try {
      const data = await discoverySeason(searchYear, searchSeason)
      setResults(data)
      setYear(searchYear)
      setSeason(searchSeason)
      saveCache({ year: searchYear, season: searchSeason, results: data, timestamp: Date.now() })
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : t.common.error)
    } finally {
      setLoading(false)
    }
  }

  function getAnimeKey(anime: DiscoveryAnime): number {
    return anime.bangumi_id || anime.anilist_id || 0
  }

  function isSubscribed(anime: DiscoveryAnime): boolean {
    const key = getAnimeKey(anime)
    if (!key) return false
    return subscriptions.some(
      (sub) => sub.bangumi_id === key || sub.anilist_id === key
    )
  }

  async function handleSubscribe(anime: DiscoveryAnime) {
    const key = getAnimeKey(anime)
    if (!key) {
      setError(t.discovery.missingAnilistId)
      return
    }
    setSubscribing((prev) => new Set(prev).add(key))
    try {
      const payload: SubscriptionCreateRequest = {
        anilist_id: anime.anilist_id,
        bangumi_id: anime.bangumi_id,
        title_romaji: anime.title_romaji || anime.title_english || t.discovery.unknown,
        title_native: anime.title_native || null,
        title_chinese: anime.title_chinese,
        total_episodes: anime.total_episodes || 12,
        season_year: anime.season_year || year,
        season: anime.season || season,
      }
      await discoverySubscribe(payload)
      // Refresh subscriptions to update "already subscribed" status
      listSubscriptions().then(setSubscriptions).catch(() => {})
    } catch (err) {
      setError(err instanceof Error ? err.message : t.common.error)
    } finally {
      setSubscribing((prev) => {
        const next = new Set(prev)
        next.delete(key)
        return next
      })
    }
  }

  const seasonOptions = SEASONS.map((s) => ({
    value: s,
    label: t.discovery.seasons[s as keyof typeof t.discovery.seasons],
  }))

  const typeOptions = [
    { value: '', label: t.discovery.allTypes },
    { value: 'TV', label: 'TV' },
    { value: 'MOVIE', label: 'MOVIE' },
    { value: 'OVA', label: 'OVA' },
    { value: 'ONA', label: 'ONA' },
  ]

  // Apply filters
  const filteredResults = results.filter((item) => {
    // Type filter
    if (typeFilter && item.format !== typeFilter) return false
    // Search filter
    if (searchQuery) {
      const q = searchQuery.toLowerCase()
      const title = (item.title_chinese || item.title_native || item.title_romaji || item.title_english || '').toLowerCase()
      if (!title.includes(q)) return false
    }
    return true
  })

  const currentSeasonLabel = t.discovery.seasons[season as keyof typeof t.discovery.seasons]

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-white">
            {t.discovery.title}
          </h1>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
            {year} {currentSeasonLabel} · {results.length} {t.discovery.animeCount}
          </p>
        </div>
      </div>

      {/* Error banner */}
      {error && (
        <Card className="border-rose-200 bg-rose-50 dark:border-rose-800 dark:bg-rose-950/30">
          <p className="text-sm text-rose-600 dark:text-rose-400">{error}</p>
        </Card>
      )}

      {/* Search & filters */}
      <Card>
        <div className="space-y-4">
          {/* Row 1: Season selector */}
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <Input
              label={t.discovery.year}
              type="number"
              value={year}
              onChange={(e) => setYear(Number(e.target.value))}
            />
            <Select
              label={t.discovery.season}
              options={seasonOptions}
              value={season}
              onChange={(e) => setSeason(e.target.value)}
            />
            <div className="flex items-end">
              <Button onClick={() => handleSearch()} disabled={loading} isLoading={loading} className="w-full">
                <Search className="h-4 w-4" />
                {loading ? t.discovery.searching : t.discovery.search}
              </Button>
            </div>
          </div>

          {/* Row 2: Filters (only show when results exist) */}
          {results.length > 0 && (
            <div className="flex items-center gap-3 border-t border-slate-100 dark:border-slate-800 pt-4">
              <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                <input
                  type="text"
                  placeholder={t.discovery.searchPlaceholder}
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full rounded-xl border border-slate-200 bg-white py-2.5 pl-10 pr-4 text-sm text-slate-900 placeholder:text-slate-400 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 dark:border-slate-700 dark:bg-slate-900 dark:text-white dark:placeholder:text-slate-500"
                />
                {searchQuery && (
                  <button
                    onClick={() => setSearchQuery('')}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
                  >
                    <X className="h-4 w-4" />
                  </button>
                )}
              </div>
              <div className="flex gap-1.5">
                {typeOptions.map((opt) => (
                  <button
                    key={opt.value}
                    onClick={() => setTypeFilter(typeFilter === opt.value ? '' : opt.value)}
                    className={`rounded-lg px-3 py-2 text-xs font-medium transition-colors ${
                      typeFilter === opt.value
                        ? 'bg-indigo-100 text-indigo-700 dark:bg-indigo-500/20 dark:text-indigo-300'
                        : 'bg-slate-100 text-slate-600 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-400 dark:hover:bg-slate-700'
                    }`}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      </Card>

      {/* Results */}
      {loading ? (
        <Loading message={t.discovery.searching} />
      ) : filteredResults.length === 0 ? (
        <EmptyState
          title={results.length > 0 ? t.discovery.noMatch : t.discovery.noResults}
          description={results.length > 0 ? t.discovery.tryDifferentFilter : undefined}
          icon={<Compass className="h-8 w-8" />}
        />
      ) : (
        <div className="space-y-3">
          {filteredResults.map((item) => (
            <Card key={getAnimeKey(item) || item.title_romaji} hover>
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <h3 className="text-base font-semibold text-slate-900 dark:text-white">
                      {item.title_chinese || item.title_native || item.title_romaji || item.title_english || t.discovery.unknown}
                    </h3>
                    {item.format && (
                      <Badge variant="primary">
                        {item.format}
                      </Badge>
                    )}
                    {item.total_episodes && (
                      <Badge variant="muted">
                        {item.total_episodes} EP
                      </Badge>
                    )}
                  </div>
                  {item.title_romaji && (item.title_chinese || item.title_native) && (
                    <p className="mt-0.5 text-sm text-slate-500 dark:text-slate-400">
                      {item.title_romaji}
                    </p>
                  )}
                </div>
                <div className="shrink-0">
                  {item.filtered ? (
                    <div className="flex items-center gap-2">
                      <Filter className="h-4 w-4 text-slate-400" />
                      <Badge variant="warning">
                        {t.discovery.filtered}: {item.filter_reason}
                      </Badge>
                    </div>
                  ) : isSubscribed(item) ? (
                    <Badge variant="success">
                      ✓ {t.discovery.subscribed}
                    </Badge>
                  ) : (
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={() => handleSubscribe(item)}
                      disabled={subscribing.has(getAnimeKey(item))}
                      isLoading={subscribing.has(getAnimeKey(item))}
                    >
                      <Plus className="h-3.5 w-3.5" />
                      {subscribing.has(getAnimeKey(item)) ? t.discovery.subscribing : t.discovery.subscribe}
                    </Button>
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

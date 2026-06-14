import { useState } from 'react'
import { Search } from 'lucide-react'
import { searchAnime } from '../api/client'
import type { AnimeLookup } from '../types'
import { useI18n } from '../i18n/useI18n'
import { Button, Input, Loading, Modal } from './ui'

interface AnimeSearchDialogProps {
  open: boolean
  onClose: () => void
  onSelect: (candidate: AnimeLookup) => void
}

export function AnimeSearchDialog({ open, onClose, onSelect }: AnimeSearchDialogProps) {
  const { t } = useI18n()
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<AnimeLookup[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  if (!open) return null

  async function handleSearch() {
    if (!query.trim()) return
    setLoading(true)
    setError(null)
    setResults([])
    try {
      const { candidates } = await searchAnime(query.trim())
      setResults(candidates)
      if (candidates.length === 0) {
        setError(t.subscriptions.noResults)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : t.common.error)
    } finally {
      setLoading(false)
    }
  }

  function handleSelect(candidate: AnimeLookup) {
    onSelect(candidate)
    setQuery('')
    setResults([])
    setError(null)
    onClose()
  }

  return (
    <Modal
      title={t.subscriptions.searchByTitle}
      onClose={onClose}
      size="lg"
    >
      <div className="space-y-4">
        <div className="flex items-end gap-2">
          <Input
            placeholder={t.subscriptions.titlePlaceholder}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                e.preventDefault()
                void handleSearch()
              }
            }}
            className="flex-1"
          />
          <Button
            variant="primary"
            onClick={() => void handleSearch()}
            isLoading={loading}
            disabled={!query.trim()}
          >
            <Search className="h-4 w-4" />
            {t.common.search}
          </Button>
        </div>

        {error && (
          <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-600 dark:border-rose-800 dark:bg-rose-950/30 dark:text-rose-400">
            {error}
          </div>
        )}

        {loading && <Loading message={t.common.loading} />}

        <div className="max-h-[50vh] space-y-2 overflow-y-auto">
          {results.map((candidate, index) => (
            <button
              key={`${candidate.bangumi_id ?? candidate.anilist_id ?? index}`}
              type="button"
              onClick={() => handleSelect(candidate)}
              className="w-full rounded-xl border border-slate-100 bg-slate-50/50 p-4 text-left transition-colors hover:bg-slate-100 dark:border-slate-800 dark:bg-slate-800/30 dark:hover:bg-slate-800"
            >
              <p className="font-medium text-slate-900 dark:text-white">
                {candidate.title_chinese || candidate.title_native || candidate.title_romaji || candidate.title_english || t.discovery.unknown}
              </p>
              <p className="mt-0.5 text-sm text-slate-500 dark:text-slate-400">
                {[candidate.title_native, candidate.title_romaji, candidate.title_english]
                  .filter(Boolean)
                  .join(' / ')}
              </p>
              <div className="mt-2 flex flex-wrap gap-2 text-xs text-slate-400 dark:text-slate-500">
                {candidate.bangumi_id && <span>Bangumi: {candidate.bangumi_id}</span>}
                {candidate.anilist_id && <span>AniList: {candidate.anilist_id}</span>}
                {candidate.tmdb_id && <span>TMDB: {candidate.tmdb_id}</span>}
                {candidate.total_episodes && <span>{candidate.total_episodes} eps</span>}
              </div>
            </button>
          ))}
        </div>
      </div>
    </Modal>
  )
}

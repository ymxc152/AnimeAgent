import type { AnimeLookup } from '../types'
import { useI18n } from '../i18n/useI18n'
import { Loading, Modal } from './ui'

interface AnimeCandidateDialogProps {
  open: boolean
  title?: string
  candidates: AnimeLookup[]
  loading: boolean
  error: string | null
  onClose: () => void
  onSelect: (candidate: AnimeLookup) => void
}

export function AnimeCandidateDialog({
  open,
  title,
  candidates,
  loading,
  error,
  onClose,
  onSelect,
}: AnimeCandidateDialogProps) {
  const { t } = useI18n()

  if (!open) return null

  function handleSelect(candidate: AnimeLookup) {
    onSelect(candidate)
    onClose()
  }

  return (
    <Modal
      title={title || t.subscriptions.selectCandidateTitle}
      onClose={onClose}
      size="lg"
    >
      <div className="space-y-4">
        {error && (
          <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-600 dark:border-rose-800 dark:bg-rose-950/30 dark:text-rose-400">
            {error}
          </div>
        )}

        {loading && <Loading message={t.common.loading} />}

        {!loading && candidates.length === 0 && !error && (
          <div className="rounded-xl border border-slate-100 bg-slate-50/50 px-4 py-8 text-center text-sm text-slate-500 dark:border-slate-800 dark:bg-slate-800/30 dark:text-slate-400">
            {t.subscriptions.noResults}
          </div>
        )}

        <div className="max-h-[50vh] space-y-2 overflow-y-auto">
          {candidates.map((candidate, index) => (
            <button
              key={`${candidate.bangumi_id ?? candidate.anilist_id ?? candidate.tmdb_id ?? index}`}
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

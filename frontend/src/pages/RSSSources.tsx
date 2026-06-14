import { useCallback, useEffect, useState } from 'react'
import { createRSSSource, deleteRSSSource, listRSSSources, updateRSSSource } from '../api/client'
import type { RSSSource } from '../types'
import { useI18n } from '../i18n/useI18n'
import { usePolling } from '../hooks/usePolling'
import { useToast } from '../hooks/useToast'
import { Card, Button, Input, Switch, Badge, EmptyState, Modal, SkeletonCard } from '../components/ui'
import { Rss, Plus, Pencil, Trash2, X } from 'lucide-react'

interface FormData {
  name: string
  url: string
  includeKeywords: string
  excludeKeywords: string
  is_active: boolean
}

/** Convert comma-separated keywords to JSON parser_rules string */
function toParserRules(include: string, exclude: string): string | null {
  const inc = include.split(',').map(s => s.trim()).filter(Boolean)
  const exc = exclude.split(',').map(s => s.trim()).filter(Boolean)
  if (inc.length === 0 && exc.length === 0) return null
  const rules: Record<string, string[]> = {}
  if (inc.length > 0) rules.include = inc
  if (exc.length > 0) rules.exclude = exc
  return JSON.stringify(rules)
}

/** Parse JSON parser_rules string to comma-separated keywords */
function fromParserRules(rules: string | null): { include: string; exclude: string } {
  if (!rules) return { include: '', exclude: '' }
  try {
    const parsed = JSON.parse(rules)
    return {
      include: (parsed.include || []).join(', '),
      exclude: (parsed.exclude || []).join(', '),
    }
  } catch {
    return { include: '', exclude: '' }
  }
}

const EMPTY_FORM: FormData = {
  name: '',
  url: '',
  includeKeywords: '',
  excludeKeywords: '',
  is_active: true,
}

export function RSSSources() {
  const { t } = useI18n()
  const { showToast } = useToast()
  const [sources, setSources] = useState<RSSSource[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [form, setForm] = useState<FormData>(EMPTY_FORM)
  const [editing, setEditing] = useState<RSSSource | null>(null)
  const [showModal, setShowModal] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const data = await listRSSSources()
      setSources(data)
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load')
    } finally {
      setLoading(false)
    }
  }, [])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- initial data load
  useEffect(() => { void load() }, [load])
  usePolling(load, 10000)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    const parser_rules = toParserRules(form.includeKeywords, form.excludeKeywords)
    try {
      if (editing) {
        await updateRSSSource(editing.id, {
          name: form.name,
          url: form.url,
          parser_rules,
          is_active: form.is_active,
        })
      } else {
        await createRSSSource({
          name: form.name,
          url: form.url,
          parser_rules,
          is_active: form.is_active,
        })
      }
      resetForm()
      setShowModal(false)
      await load()
      showToast(t.rssSources.saveSuccess)
    } catch (err) {
      setError(err instanceof Error ? err.message : t.rssSources.saveError)
    }
  }

  async function handleDelete(id: number) {
    if (!confirm(t.rssSources.deleteConfirm)) return
    try {
      await deleteRSSSource(id)
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : t.rssSources.deleteError)
    }
  }

  function resetForm() {
    setEditing(null)
    setForm(EMPTY_FORM)
  }

  function startEdit(source: RSSSource) {
    const { include, exclude } = fromParserRules(source.parser_rules)
    setEditing(source)
    setForm({
      name: source.name,
      url: source.url,
      includeKeywords: include,
      excludeKeywords: exclude,
      is_active: source.is_active,
    })
    setShowModal(true)
  }

  function startAdd() {
    resetForm()
    setShowModal(true)
  }

  /** Render parser_rules as human-readable badges */
  function renderRules(rules: string | null) {
    if (!rules) return null
    const { include, exclude } = fromParserRules(rules)
    const parts: { label: string; variant: 'success' | 'danger' }[] = []
    if (include) parts.push(...include.split(',').map(k => ({ label: `+${k.trim()}`, variant: 'success' as const })))
    if (exclude) parts.push(...exclude.split(',').map(k => ({ label: `-${k.trim()}`, variant: 'danger' as const })))
    if (parts.length === 0) return null
    return (
      <div className="mt-1 flex flex-wrap gap-1">
        {parts.map((p, i) => (
          <Badge key={i} variant={p.variant} size="sm">{p.label}</Badge>
        ))}
      </div>
    )
  }

  if (loading) {
    return (
      <div className="space-y-8">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-white">
            {t.rssSources.title}
          </h1>
        </div>
        <div className="space-y-3">
          <SkeletonCard />
          <SkeletonCard />
          <SkeletonCard />
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-8">
      {/* Page header */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-white">
          {t.rssSources.title}
        </h1>
        <Button variant="primary" onClick={startAdd}>
          <Plus className="h-4 w-4" />
          {t.common.add}
        </Button>
      </div>

      {/* Error banner */}
      {error && (
        <Card className="border-rose-200 bg-rose-50 dark:border-rose-800 dark:bg-rose-950/30">
          <p className="text-sm text-rose-600 dark:text-rose-400">{error}</p>
        </Card>
      )}

      {/* Source list */}
      {sources.length === 0 ? (
        <Card padding="lg">
          <EmptyState
            title={t.rssSources.noSources}
            icon={<Rss className="h-8 w-8" />}
          />
        </Card>
      ) : (
        <div className="space-y-3">
          {sources.map((source) => (
            <Card key={source.id} hover>
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <h3 className="text-base font-semibold text-slate-900 dark:text-white">
                      {source.name}
                    </h3>
                    <Badge variant={source.is_active ? 'success' : 'muted'}>
                      {source.is_active ? t.common.active : t.common.inactive}
                    </Badge>
                  </div>
                  <p className="mt-0.5 truncate text-sm text-slate-500 dark:text-slate-400">
                    {source.url}
                  </p>
                  {renderRules(source.parser_rules)}
                </div>
                <div className="flex shrink-0 items-center gap-2">
                  <Button variant="secondary" size="sm" onClick={() => startEdit(source)}>
                    <Pencil className="h-3.5 w-3.5" />
                    {t.common.edit}
                  </Button>
                  <Button variant="danger" size="sm" onClick={() => handleDelete(source.id)}>
                    <Trash2 className="h-3.5 w-3.5" />
                    {t.common.delete}
                  </Button>
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}


      {/* Add/Edit modal */}
      {showModal && (
        <Modal
          title={editing ? t.rssSources.editTitle : t.rssSources.addTitle}
          onClose={() => { setShowModal(false); resetForm() }}
        >
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Input
                label={t.rssSources.form.name}
                placeholder={t.rssSources.form.namePlaceholder}
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                required
              />
              <Input
                label={t.rssSources.form.url}
                placeholder={t.rssSources.form.urlPlaceholder}
                value={form.url}
                onChange={(e) => setForm({ ...form, url: e.target.value })}
                required
              />
            </div>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Input
                label={t.rssSources.form.includeKeywords}
                placeholder={t.rssSources.form.includePlaceholder}
                value={form.includeKeywords}
                onChange={(e) => setForm({ ...form, includeKeywords: e.target.value })}
              />
              <Input
                label={t.rssSources.form.excludeKeywords}
                placeholder={t.rssSources.form.excludePlaceholder}
                value={form.excludeKeywords}
                onChange={(e) => setForm({ ...form, excludeKeywords: e.target.value })}
              />
            </div>
            <div className="flex items-center gap-6">
              <Switch
                checked={form.is_active ?? true}
                onChange={(checked) => setForm({ ...form, is_active: checked })}
                label={t.rssSources.form.active}
              />
            </div>
            <div className="flex justify-end gap-3 pt-2">
              <Button type="button" variant="secondary" onClick={() => { setShowModal(false); resetForm() }}>
                <X className="h-4 w-4" />
                {t.common.cancel}
              </Button>
              <Button type="submit" variant="primary">
                {editing ? (
                  <>
                    <Pencil className="h-4 w-4" />
                    {t.common.update}
                  </>
                ) : (
                  <>
                    <Plus className="h-4 w-4" />
                    {t.common.add}
                  </>
                )}
              </Button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  )
}

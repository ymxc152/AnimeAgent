import { useCallback, useEffect, useState } from 'react'
import { listLogs } from '../api/client'
import { useI18n } from '../i18n/useI18n'
import { usePolling } from '../hooks/usePolling'
import { Card, Button, Input, Loading, EmptyState, FloatingActionButton } from '../components/ui'
import { ScrollText, RefreshCw } from 'lucide-react'

export function Logs() {
  const { t } = useI18n()
  const [logs, setLogs] = useState<string[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [limit, setLimit] = useState(100)

   
  const load = useCallback(async () => {
    setLoading(true)
    try {
      const data = await listLogs(limit)
      setLogs(data)
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load')
    } finally {
      setLoading(false)
    }
  }, [limit])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- initial data load
  useEffect(() => { void load() }, [load])
  usePolling(load, 10000)

  return (
    <div className="space-y-8">
      {/* Page header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-white">
          {t.logs.title}
        </h1>
      </div>

      {/* Error banner */}
      {error && (
        <Card className="border-rose-200 bg-rose-50 dark:border-rose-800 dark:bg-rose-950/30">
          <p className="text-sm text-rose-600 dark:text-rose-400">{error}</p>
        </Card>
      )}

      {/* Controls */}
      <Card>
        <div className="flex items-end gap-4">
          <Input
            label={t.logs.limit}
            type="number"
            value={limit}
            onChange={(e) => setLimit(Number(e.target.value))}
            className="!w-32"
          />
          <Button variant="secondary" onClick={load} isLoading={loading}>
            <RefreshCw className="h-4 w-4" />
            {t.logs.refresh}
          </Button>
        </div>
      </Card>

      {/* Log content */}
      {loading ? (
        <Loading message={t.common.loading} card />
      ) : logs.length === 0 ? (
        <Card padding="lg">
          <EmptyState
            title={t.logs.noLogs}
            icon={<ScrollText className="h-8 w-8" />}
          />
        </Card>
      ) : (
        <Card padding="none">
          <pre className="max-h-[70vh] overflow-auto p-5 font-mono text-xs leading-relaxed text-slate-700 dark:text-slate-300">
            {logs.join('\n')}
          </pre>
        </Card>
      )}

      <FloatingActionButton
        position="bottom-left"
        variant="secondary"
        icon={<RefreshCw className="h-5 w-5" />}
        title={t.common.retry}
        onClick={() => void load()}
      />
    </div>
  )
}

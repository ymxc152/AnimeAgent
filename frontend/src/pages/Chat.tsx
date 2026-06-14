import { useCallback, useEffect, useRef, useState } from 'react'
import { MessageCircle, Send, Plus, Trash2 } from 'lucide-react'
import { sendChatMessage, clearChatHistory } from '../api/client'
import { useI18n } from '../i18n/useI18n'
import { Badge, Button, Card, EmptyState } from '../components/ui'
import type { ChatMessage } from '../types'

const INTENT_VARIANT: Record<string, 'primary' | 'success' | 'warning' | 'info' | 'default'> = {
  query_status: 'info',
  subscribe: 'success',
  select_candidate: 'success',
  retry_episode: 'warning',
  help: 'primary',
}

export function Chat() {
  const { t } = useI18n()
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  // Auto-scroll on new messages
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  const handleSend = useCallback(async () => {
    const text = input.trim()
    if (!text || loading) return

    setInput('')
    setError(null)

    // Optimistic user message
    const userMsg: ChatMessage = {
      role: 'user',
      content: text,
      created_at: new Date().toISOString(),
    }
    setMessages((prev) => [...prev, userMsg])
    setLoading(true)

    try {
      const reply = await sendChatMessage(text, sessionId ?? undefined)
      setSessionId(reply.session_id)

      const assistantMsg: ChatMessage = {
        role: 'assistant',
        content: reply.reply,
        intent: reply.intent,
        created_at: new Date().toISOString(),
      }
      setMessages((prev) => [...prev, assistantMsg])
    } catch (err) {
      setError(err instanceof Error ? err.message : t.common.error)
      // Remove optimistic user message on error
      setMessages((prev) => prev.slice(0, -1))
    } finally {
      setLoading(false)
      inputRef.current?.focus()
    }
  }, [input, loading, sessionId, t.common.error])

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault()
        void handleSend()
      }
    },
    [handleSend]
  )

  const handleNewChat = useCallback(() => {
    setMessages([])
    setSessionId(null)
    setError(null)
    setInput('')
  }, [])

  const handleClearHistory = useCallback(async () => {
    if (!sessionId) return
    try {
      await clearChatHistory(sessionId)
    } catch {
      // ignore
    }
    handleNewChat()
  }, [sessionId, handleNewChat])

  return (
    <div className="flex h-[calc(100vh-12rem)] flex-col space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-violet-600 to-indigo-600 text-white shadow-lg shadow-indigo-500/25">
            <MessageCircle className="h-5 w-5" />
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-white">
            {t.chat.title}
          </h1>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="sm" onClick={handleNewChat}>
            <Plus className="mr-1.5 h-4 w-4" />
            {t.chat.newChat}
          </Button>
          {sessionId && (
            <Button variant="ghost" size="sm" onClick={() => void handleClearHistory()}>
              <Trash2 className="mr-1.5 h-4 w-4" />
              {t.chat.clearHistory}
            </Button>
          )}
        </div>
      </div>

      {/* Messages area */}
      <Card className="flex min-h-0 flex-1 flex-col overflow-hidden !p-0">
        <div className="flex-1 overflow-y-auto p-4">
          {messages.length === 0 && !loading ? (
            <EmptyState
              title={t.chat.title}
              description={t.chat.placeholder}
              icon={<MessageCircle className="h-12 w-12 text-slate-300 dark:text-slate-600" />}
            />
          ) : (
            <div className="flex flex-col gap-3">
              {messages.map((msg, i) => (
                <MessageBubble
                  key={i}
                  message={msg}
                  intentLabels={t.chat.intentLabels}
                  intentVariant={INTENT_VARIANT}
                />
              ))}
              {loading && (
                <div className="flex max-w-[80%] items-start gap-2 self-start">
                  <div className="rounded-2xl bg-slate-100 px-4 py-3 dark:bg-slate-800">
                    <div className="flex items-center gap-2 text-sm text-slate-500 dark:text-slate-400">
                      <span className="inline-block h-2 w-2 animate-bounce rounded-full bg-indigo-400 [animation-delay:0ms]" />
                      <span className="inline-block h-2 w-2 animate-bounce rounded-full bg-indigo-400 [animation-delay:150ms]" />
                      <span className="inline-block h-2 w-2 animate-bounce rounded-full bg-indigo-400 [animation-delay:300ms]" />
                      <span className="ml-1">{t.chat.thinking}</span>
                    </div>
                  </div>
                </div>
              )}
              <div ref={bottomRef} />
            </div>
          )}
        </div>

        {/* Error banner */}
        {error && (
          <div className="border-t border-rose-200 bg-rose-50 px-4 py-2 text-sm text-rose-700 dark:border-rose-800 dark:bg-rose-900/20 dark:text-rose-300">
            {error}
          </div>
        )}

        {/* Input bar */}
        <div className="border-t border-slate-200 bg-white p-3 dark:border-slate-700 dark:bg-slate-900">
          <div className="flex items-center gap-2">
            <input
              ref={inputRef}
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={t.chat.placeholder}
              disabled={loading}
              className="flex-1 rounded-xl border border-slate-200 bg-slate-50 px-4 py-2.5 text-sm text-slate-900 placeholder:text-slate-400 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 disabled:cursor-not-allowed disabled:opacity-60 dark:border-slate-700 dark:bg-slate-800 dark:text-white dark:placeholder:text-slate-500 dark:focus:border-indigo-400"
            />
            <Button
              variant="primary"
              size="md"
              onClick={() => void handleSend()}
              disabled={!input.trim() || loading}
            >
              <Send className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </Card>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Message bubble
// ---------------------------------------------------------------------------

function MessageBubble({
  message,
  intentLabels,
  intentVariant,
}: {
  message: ChatMessage
  intentLabels: Record<string, string>
  intentVariant: Record<string, string>
}) {
  const isUser = message.role === 'user'
  const intentAction = message.intent?.action as string | undefined
  const label = intentAction ? intentLabels[intentAction] : undefined
  const variant = intentAction ? intentVariant[intentAction] ?? 'default' : 'default'

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div
        className={`max-w-[80%] rounded-2xl px-4 py-3 ${
          isUser
            ? 'bg-indigo-500 text-white'
            : 'bg-white text-slate-900 shadow-sm ring-1 ring-slate-200 dark:bg-slate-800 dark:text-white dark:ring-slate-700'
        }`}
      >
        <p className="whitespace-pre-wrap text-sm leading-relaxed">{message.content}</p>
        {label && (
          <div className="mt-2">
            <Badge variant={variant as 'primary' | 'success' | 'warning' | 'info' | 'default'} size="sm">
              {label}
            </Badge>
          </div>
        )}
      </div>
    </div>
  )
}

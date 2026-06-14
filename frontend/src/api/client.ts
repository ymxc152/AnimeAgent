import axios, { AxiosError } from 'axios'
import type {
  AnimeLookup,
  AnimeSearchResponse,
  AutoSubscribeRule,
  AutoSubscribeRuleCreateRequest,
  AutoSubscribeRuleUpdateRequest,
  ChatHistory,
  ChatReply,
  DiscoveryAnime,
  Episode,
  EpisodeDetail,
  HumanInputRequest,
  RSSSource,
  RSSSourceCreateRequest,
  RSSSourceUpdateRequest,
  Stats,
  Subscription,
  SubscriptionCreateRequest,
  ToolHealth,
} from '../types'

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api'

export const api = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json',
  },
})

api.interceptors.response.use(
  (response) => response,
  (error: AxiosError<{ detail?: string }>) => {
    const message = error.response?.data?.detail || error.message
    return Promise.reject(new Error(message))
  }
)

export async function getHealth(): Promise<{ status: string }> {
  const { data } = await api.get('/health')
  return data
}

export async function getStats(): Promise<Stats> {
  const { data } = await api.get('/stats')
  return data
}

export async function listSubscriptions(): Promise<Subscription[]> {
  const { data } = await api.get('/subscriptions')
  return data
}

export async function createSubscription(payload: SubscriptionCreateRequest): Promise<Subscription> {
  const { data } = await api.post('/subscriptions', payload)
  return data
}

export async function updateSubscription(
  id: number,
  payload: Partial<Subscription>
): Promise<Subscription> {
  const { data } = await api.patch(`/subscriptions/${id}`, payload)
  return data
}

export async function deleteSubscription(id: number): Promise<void> {
  await api.delete(`/subscriptions/${id}`)
}

export async function refreshSubscriptionMetadata(id: number): Promise<Subscription> {
  const { data } = await api.post(`/subscriptions/${id}/refresh-metadata`)
  return data
}

export async function listEpisodes(subscriptionId?: number, status?: string[]): Promise<Episode[]> {
  const params: Record<string, string | number> = {}
  if (subscriptionId !== undefined) params.subscription_id = subscriptionId
  if (status && status.length > 0) params.status = status.join(',')
  const { data } = await api.get('/episodes', { params })
  return data
}

export async function getEpisodeDetail(id: number): Promise<EpisodeDetail> {
  const { data } = await api.get(`/episodes/${id}`)
  return data
}

export async function retryEpisode(id: number): Promise<Episode> {
  const { data } = await api.post(`/episodes/${id}/retry`)
  return data
}

export async function submitHumanInput(
  id: number,
  payload: HumanInputRequest
): Promise<Episode> {
  const { data } = await api.post(`/episodes/${id}/human_input`, payload)
  return data
}

export async function lookupAnime(source: 'bangumi' | 'anilist' | 'tmdb', id: number): Promise<AnimeLookup> {
  const { data } = await api.get('/anime/lookup', { params: { source, id } })
  return data
}

export async function searchAnime(query: string): Promise<AnimeSearchResponse> {
  const { data } = await api.get('/anime/search', { params: { query } })
  return data
}

export async function discoverySeason(
  year: number,
  season: string,
  applyFilters = true,
  search?: string
): Promise<DiscoveryAnime[]> {
  const params: Record<string, string | number | boolean> = { year, season, apply_filters: applyFilters }
  if (search) params.search = search
  const { data } = await api.get('/discovery/season', { params })
  return data
}

export async function discoverySubscribe(payload: SubscriptionCreateRequest): Promise<Subscription> {
  const { data } = await api.post('/discovery/subscribe', payload)
  return data
}

export async function listRSSSources(): Promise<RSSSource[]> {
  const { data } = await api.get('/rss-sources')
  return data
}

export async function createRSSSource(payload: RSSSourceCreateRequest): Promise<RSSSource> {
  const { data } = await api.post('/rss-sources', payload)
  return data
}

export async function updateRSSSource(
  id: number,
  payload: RSSSourceUpdateRequest
): Promise<RSSSource> {
  const { data } = await api.patch(`/rss-sources/${id}`, payload)
  return data
}

export async function deleteRSSSource(id: number): Promise<void> {
  await api.delete(`/rss-sources/${id}`)
}

export async function listLogs(limit = 100): Promise<string[]> {
  const { data } = await api.get('/logs', { params: { limit } })
  return data
}

export async function getToolsHealth(): Promise<Record<string, ToolHealth>> {
  const { data } = await api.get('/tools/health')
  return data
}

export async function listAutoSubscribeRules(): Promise<AutoSubscribeRule[]> {
  const { data } = await api.get('/auto-subscribe-rules')
  return data
}

export async function createAutoSubscribeRule(payload: AutoSubscribeRuleCreateRequest): Promise<AutoSubscribeRule> {
  const { data } = await api.post('/auto-subscribe-rules', payload)
  return data
}

export async function updateAutoSubscribeRule(
  id: number,
  payload: AutoSubscribeRuleUpdateRequest
): Promise<AutoSubscribeRule> {
  const { data } = await api.patch(`/auto-subscribe-rules/${id}`, payload)
  return data
}

export async function deleteAutoSubscribeRule(id: number): Promise<void> {
  await api.delete(`/auto-subscribe-rules/${id}`)
}

export async function sendChatMessage(message: string, sessionId?: string): Promise<ChatReply> {
  const { data } = await api.post('/chat', { message, session_id: sessionId })
  return data
}

export async function getChatHistory(sessionId: string): Promise<ChatHistory> {
  const { data } = await api.get('/chat/history', { params: { session_id: sessionId } })
  return data
}

export async function clearChatHistory(sessionId: string): Promise<void> {
  await api.delete('/chat/history', { params: { session_id: sessionId } })
}

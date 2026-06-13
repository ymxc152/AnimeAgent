import axios, { AxiosError } from 'axios'
import type {
  DiscoveryAnime,
  Episode,
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

export async function listEpisodes(subscriptionId?: number, status?: string): Promise<Episode[]> {
  const params: Record<string, string | number> = {}
  if (subscriptionId !== undefined) params.subscription_id = subscriptionId
  if (status) params.status = status
  const { data } = await api.get('/episodes', { params })
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

export async function discoverySeason(
  year: number,
  season: string,
  applyFilters = true
): Promise<DiscoveryAnime[]> {
  const { data } = await api.get('/discovery/season', {
    params: { year, season, apply_filters: applyFilters },
  })
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

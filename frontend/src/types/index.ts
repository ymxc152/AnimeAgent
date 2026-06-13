export interface Subscription {
  id: number
  bangumi_id: number | null
  anilist_id: number | null
  title_romaji: string
  title_native: string | null
  title_chinese: string | null
  season_year: number | null
  season: string | null
  total_episodes: number | null
  local_folder_name: string | null
  status: string
  source: string
  auto_download_enabled: boolean
  expected_airing_weekday: number | null
  expected_airing_time: string | null
  airing_timezone: string | null
  created_at: string | null
  rss_source_id: number | null
  ep_total: number
  ep_completed: number
  ep_downloaded: number
  ep_failed: number
  ep_pending: number
}

export interface Episode {
  id: number
  subscription_id: number
  subscription_title: string | null
  episode_number: number
  title: string | null
  aired_at: string | null
  status: string
  content_type: string
  torrent_hash: string | null
  torrent_info_hash: string | null
  torrent_title: string | null
  torrent_name: string | null
  torrent_link: string | null
  torrent_status: string | null
  torrent_last_speed: number
  torrent_added_at: string | null
  torrent_checked_at: string | null
  download_path: string | null
  organized_path: string | null
  metadata_verified: boolean
  error_log: string | null
  torrent_candidates_count: number
  created_at: string | null
  updated_at: string | null
}

export interface EpisodeDetail extends Episode {
  torrent_candidates: Array<Record<string, unknown>>
  torrent_failed_hashes: string[]
}

export interface RSSSource {
  id: number
  name: string
  url: string
  parser_rules: string | null
  is_active: boolean
}

export interface Stats {
  subscriptions: {
    total: number
    ongoing: number
    completed: number
  }
  episodes: {
    pending: number
    completed: number
    failed: number
  }
}

export interface ToolHealth {
  healthy: boolean
  detail: string
}

export interface DiscoveryAnime {
  anilist_id: number | null
  bangumi_id: number | null
  title_romaji: string | null
  title_native: string | null
  title_chinese: string | null
  title_english: string | null
  format: string | null
  total_episodes: number | null
  season_year: number | null
  season: string | null
  filtered: boolean
  filter_reason: string | null
}

export interface AnimeLookup {
  bangumi_id: number | null
  anilist_id: number | null
  title_romaji: string | null
  title_native: string | null
  title_chinese: string | null
  title_english: string | null
  format: string | null
  total_episodes: number | null
  season_year: number | null
  season: string | null
}

export interface HumanInputRequest {
  action: 'approve' | 'reject'
  torrent_link?: string | null
}

export interface SubscriptionCreateRequest {
  bangumi_id?: number | null
  anilist_id?: number | null
  title_romaji: string
  title_native?: string | null
  title_chinese?: string | null
  season_year?: number | null
  season?: string | null
  total_episodes?: number | null
  local_folder_name?: string | null
  auto_download_enabled?: boolean
  rss_source_id?: number | null
}

export interface RSSSourceCreateRequest {
  name: string
  url: string
  parser_rules?: string | null
  is_active?: boolean
}

export interface RSSSourceUpdateRequest {
  name?: string | null
  url?: string | null
  parser_rules?: string | null
  is_active?: boolean | null
}

export interface AutoSubscribeRule {
  id: number
  name: string
  include_genres: string | null
  exclude_genres: string | null
  include_formats: string | null
  exclude_formats: string | null
  include_keywords: string | null
  exclude_keywords: string | null
  min_score: number | null
  use_llm: boolean
  enabled: boolean
  created_at: string | null
  updated_at: string | null
}

export interface AutoSubscribeRuleCreateRequest {
  name: string
  include_genres?: string | null
  exclude_genres?: string | null
  include_formats?: string | null
  exclude_formats?: string | null
  include_keywords?: string | null
  exclude_keywords?: string | null
  min_score?: number | null
  use_llm?: boolean
  enabled?: boolean
}

export type AutoSubscribeRuleUpdateRequest = Partial<AutoSubscribeRuleCreateRequest>

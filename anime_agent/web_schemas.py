"""Pydantic schemas for the FastAPI web panel."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class SubscriptionResponse(BaseModel):
    """Serialized subscription for API responses."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    bangumi_id: int | None
    anilist_id: int | None
    tmdb_id: int | None
    title_romaji: str
    title_native: str | None
    title_chinese: str | None
    season_year: int | None
    season: str | None
    total_episodes: int | None
    local_folder_name: str | None
    status: str
    source: str
    auto_download_enabled: bool
    expected_airing_weekday: int | None
    expected_airing_time: str | None
    airing_timezone: str | None
    created_at: datetime | None


class SubscriptionCreateRequest(BaseModel):
    """Payload to create a subscription manually."""

    bangumi_id: int | None = None
    anilist_id: int | None = None
    tmdb_id: int | None = None
    title_romaji: str
    title_native: str | None = None
    title_chinese: str | None = None
    season_year: int | None = None
    season: str | None = None
    total_episodes: int | None = None
    local_folder_name: str | None = None
    auto_download_enabled: bool = True
    rss_source_id: int | None = None


class SubscriptionUpdateRequest(BaseModel):
    """Payload to update a subscription."""

    auto_download_enabled: bool | None = None
    local_folder_name: str | None = None
    status: str | None = None


class DiscoverySubscribeRequest(BaseModel):
    """Payload to subscribe to a discovered anime."""

    anilist_id: int | None = None
    bangumi_id: int | None = None
    tmdb_id: int | None = None
    title_romaji: str
    title_native: str | None = None
    title_chinese: str | None = None
    total_episodes: int | None = None
    season_year: int | None = None
    season: str | None = None
    rss_source_id: int | None = None


class AnimeLookupResponse(BaseModel):
    """Anime metadata looked up by external ID."""

    bangumi_id: int | None = None
    anilist_id: int | None = None
    tmdb_id: int | None = None
    title_romaji: str | None = None
    title_native: str | None = None
    title_chinese: str | None = None
    title_english: str | None = None
    format: str | None = None
    total_episodes: int | None = None
    season: str | None = None
    season_year: int | None = None


class AnimeSearchResponse(BaseModel):
    """Search results for anime title queries."""

    candidates: list[AnimeLookupResponse]


class HumanInputRequest(BaseModel):
    """Payload to provide human approval for a low-confidence match."""

    action: str = "approve"  # approve / reject
    torrent_link: str | None = None  # optional magnet/torrent URL


class RSSSourceResponse(BaseModel):
    """Serialized RSS source for API responses."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    url: str
    parser_rules: str | None
    is_active: bool


class RSSSourceCreateRequest(BaseModel):
    """Payload to create an RSS source."""

    name: str
    url: str
    parser_rules: str | None = None
    is_active: bool = True


class RSSSourceUpdateRequest(BaseModel):
    """Payload to update an RSS source."""

    name: str | None = None
    url: str | None = None
    parser_rules: str | None = None
    is_active: bool | None = None


class AutoSubscribeRuleResponse(BaseModel):
    """Serialized auto-subscribe rule."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    include_genres: str | None
    exclude_genres: str | None
    include_formats: str | None
    exclude_formats: str | None
    include_keywords: str | None
    exclude_keywords: str | None
    min_score: float | None
    use_llm: bool
    enabled: bool
    created_at: datetime | None
    updated_at: datetime | None


class AutoSubscribeRuleCreateRequest(BaseModel):
    """Payload to create an auto-subscribe rule."""

    name: str
    include_genres: str | None = None
    exclude_genres: str | None = None
    include_formats: str | None = None
    exclude_formats: str | None = None
    include_keywords: str | None = None
    exclude_keywords: str | None = None
    min_score: float | None = None
    use_llm: bool = False
    enabled: bool = True


class AutoSubscribeRuleUpdateRequest(BaseModel):
    """Payload to update an auto-subscribe rule."""

    name: str | None = None
    include_genres: str | None = None
    exclude_genres: str | None = None
    include_formats: str | None = None
    exclude_formats: str | None = None
    include_keywords: str | None = None
    exclude_keywords: str | None = None
    min_score: float | None = None
    use_llm: bool | None = None
    enabled: bool | None = None


class EpisodeResponse(BaseModel):
    """Serialized episode for API responses."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    subscription_id: int
    subscription_title: str | None = None
    episode_number: int
    title: str | None
    aired_at: datetime | None
    status: str
    content_type: str
    torrent_hash: str | None
    torrent_title: str | None
    torrent_name: str | None
    torrent_link: str | None
    torrent_status: str | None
    torrent_last_speed: float
    torrent_progress: float = 0.0
    torrent_added_at: datetime | None
    torrent_checked_at: datetime | None
    download_path: str | None
    organized_path: str | None
    metadata_verified: bool
    error_log: str | None
    torrent_candidates_count: int = 0
    created_at: datetime | None
    updated_at: datetime | None


class EpisodeDetailResponse(EpisodeResponse):
    """Full episode detail including candidate list and failed hashes."""

    torrent_candidates: list[dict[str, Any]] = []
    torrent_failed_hashes: list[str] = []


class ChatRequest(BaseModel):
    """Natural-language message to the conversational agent."""

    message: str
    session_id: str | None = None


class ChatResponse(BaseModel):
    """Reply from the conversational agent."""

    reply: str
    intent: dict[str, Any]
    data: Any | None = None
    session_id: str


class ChatMessageResponse(BaseModel):
    """A single chat message in history."""

    role: str
    content: str
    intent: dict[str, Any] | None = None
    created_at: datetime


class ChatHistoryResponse(BaseModel):
    """Full conversation history for a session."""

    session_id: str
    messages: list[ChatMessageResponse]


class NotificationChannelResponse(BaseModel):
    """A notification channel as exposed to the frontend."""

    name: str
    type: str
    events: list[str]
    enabled: bool


class NotificationTestRequest(BaseModel):
    """Payload to send a test notification."""

    event_type: str = "generic"
    title: str = "AnimeAgent Test"
    body: str = "这是一条测试消息"

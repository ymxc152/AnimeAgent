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
    title_romaji: str
    title_native: str | None = None
    title_chinese: str | None = None
    total_episodes: int | None = None
    season_year: int | None = None
    season: str | None = None
    rss_source_id: int | None = None


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
    torrent_info_hash: str | None
    torrent_title: str | None
    torrent_name: str | None
    torrent_link: str | None
    torrent_status: str | None
    torrent_last_speed: float
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

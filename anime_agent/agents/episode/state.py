"""Episode Graph state definition."""

from typing import Annotated, Any, TypedDict

from langgraph.graph.message import add_messages


class EpisodeAgentState(TypedDict):
    """State for the Episode execution graph."""

    # Identity
    goal_id: str
    subscription_id: int
    episode_number: int
    rss_source_id: int | None

    # Metadata
    title_romaji: str
    title_native: str
    title_chinese: str | None
    bangumi_data: dict[str, Any]
    anilist_data: dict[str, Any]
    tmdb_data: dict[str, Any] | None

    # Execution intermediates
    season: int
    torrent_candidates: list[dict[str, Any]]
    matched_torrent: dict[str, Any] | None
    torrent_hash: str | None
    torrent_name: str | None
    torrent_failed_hashes: list[str]
    download_files: list[str]
    download_progress: float
    classification: dict[str, Any] | None
    content_type: str
    tmdb_id: int | None
    confidence: float
    verified: bool
    organized_path: str | None
    organized_files: list[str]
    emby_refreshed: bool

    # Control flow
    status: str
    errors: Annotated[list[str], add_messages]
    requires_human: bool
    human_input: str | None
    low_confidence_count: int
    resume_after: str | None  # ISO datetime for external scheduler
    resource_searched: bool  # Whether AnimeGarden search has been attempted

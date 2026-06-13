"""Pydantic Settings for AnimeAgent."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LLM
    llm_provider: str = "openai"
    openai_api_key: str | None = None
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"
    ollama_base_url: str = "http://localhost:11434/v1"
    ollama_model: str = "qwen2.5:7b"

    # qBittorrent
    qb_host: str = "http://localhost:8080"
    qb_username: str | None = None
    qb_password: str | None = None
    qb_save_path: str = "C:\\Downloads\\Anime"
    # Path mapping for remote qBittorrent. If qB reports files under a path
    # that is mounted differently on the local machine, translate it.
    # Example: remote F:\下载 -> local Z:\下载
    qb_path_map_remote: str | None = None
    qb_path_map_local: str | None = None

    # Emby
    emby_host: str = "http://localhost:8096"
    emby_api_key: str | None = None
    emby_library_name: str = "Anime"

    # TMDB
    tmdb_api_key: str | None = None
    tmdb_read_access_token: str | None = None

    # RSS
    rss_default_url: str | None = None

    # Media library
    media_library_path: str = "C:\\Media\\Anime"
    organize_template: str = "{title}\\{title} S{season:02d}E{episode:02d}.{ext}"

    # System
    check_interval_seconds: int = 600
    rss_wait_interval_seconds: int = 6 * 60 * 60  # 6 hours between RSS retries
    discovery_cron: str = "0 0 * * 1"
    log_level: str = "INFO"
    database_url: str = "sqlite+aiosqlite:///anime_agent.db"

    # Filters
    filter_exclude_ova: bool = True
    filter_exclude_movies: bool = False
    filter_min_duration_minutes: int = 5
    filter_exclude_genres_raw: str = Field(
        default="Hentai,Ecchi", validation_alias="FILTER_EXCLUDE_GENRES"
    )
    filter_exclude_formats_raw: str = Field(
        default="OVA,ONA", validation_alias="FILTER_EXCLUDE_FORMATS"
    )
    filter_require_anime_type: bool = True
    filter_auto_subscribe_new_season: bool = True

    # Discovery defaults
    discovery_default_total_episodes: int = 12

    # AnimeGarden / resource fallback
    anime_garden_base_url: str = "https://api.animes.garden"
    anime_garden_timeout_seconds: int = 30
    anime_garden_cache_ttl_seconds: int = 3600
    resource_fallback_enabled: bool = True
    resource_search_max_pages: int = 1

    # Notifications
    apprise_urls: str = ""

    @property
    def filter_exclude_genres(self) -> list[str]:
        """Genres to exclude, parsed from comma-separated env string."""
        return [g.strip() for g in self.filter_exclude_genres_raw.split(",") if g.strip()]

    @property
    def filter_exclude_formats(self) -> list[str]:
        """Formats to exclude, parsed from comma-separated env string."""
        return [f.strip() for f in self.filter_exclude_formats_raw.split(",") if f.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

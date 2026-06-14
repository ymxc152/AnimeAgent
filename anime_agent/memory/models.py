"""SQLAlchemy ORM models."""

from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class Subscription(Base):
    """A single anime season or work to track."""

    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True)
    bangumi_id = Column(Integer, unique=True, index=True)
    anilist_id = Column(Integer, unique=True, index=True)
    title_romaji = Column(String, nullable=False)
    title_native = Column(String)
    title_chinese = Column(String)
    season_year = Column(Integer)
    season = Column(String)  # WINTER/SPRING/SUMMER/FALL
    total_episodes = Column(Integer)
    local_folder_name = Column(String)  # Deprecated: use series_title instead.
    series_title = Column(String)  # Base series name, without season/sequel suffixes.
    season_number = Column(Integer, default=1)  # Numeric season (1, 2, ...) for file organization.
    status = Column(String, default="ongoing")  # ongoing/completed/dropped
    source = Column(String, default="manual")  # manual / auto_discover
    auto_download_enabled = Column(Boolean, default=True)
    rss_source_id = Column(Integer, ForeignKey("rss_sources.id"))

    expected_airing_weekday = Column(Integer)
    expected_airing_time = Column(String)
    airing_timezone = Column(String, default="Asia/Tokyo")

    created_at = Column(DateTime, default=datetime.utcnow)

    episodes = relationship("Episode", back_populates="subscription", cascade="all, delete-orphan")
    rss_source = relationship("RSSSource")
    schedules = relationship(
        "TaskSchedule", back_populates="subscription", cascade="all, delete-orphan"
    )


class Episode(Base):
    """A single episode to download."""

    __tablename__ = "episodes"

    id = Column(Integer, primary_key=True)
    subscription_id = Column(Integer, ForeignKey("subscriptions.id"), index=True)
    episode_number = Column(Integer, nullable=False)
    title = Column(String)
    aired_at = Column(DateTime)
    status = Column(String, default="pending", index=True)
    # pending/fetching/matched/downloading/completed/failed/human_review/waiting_for_rss

    torrent_hash = Column(String, index=True)
    torrent_name = Column(String)
    torrent_title = Column(String)
    torrent_info_hash = Column(String, index=True)
    torrent_link = Column(String)
    content_type = Column(String, default="TV")  # TV/SP/OVA/Movie
    download_path = Column(String)
    organized_path = Column(String)
    metadata_verified = Column(Boolean, default=False)
    error_log = Column(Text)
    human_input = Column(Text)

    torrent_candidates = Column(Text)
    torrent_candidates_last_checked_at = Column(DateTime)
    torrent_candidates_attempt_count = Column(Integer, default=0)
    low_confidence_count = Column(Integer, default=0)

    torrent_added_at = Column(DateTime)
    torrent_last_speed = Column(Float, default=0.0)
    torrent_last_speed_at = Column(DateTime)
    torrent_progress = Column(Float, default=0.0)
    torrent_status = Column(String)
    torrent_checked_at = Column(DateTime)
    torrent_failed_hashes = Column(Text)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    subscription = relationship("Subscription", back_populates="episodes")

    __table_args__ = (UniqueConstraint("subscription_id", "episode_number", name="_sub_ep_unique"),)


class MetadataMapping(Base):
    """Cross-platform metadata mapping."""

    __tablename__ = "metadata_mappings"

    id = Column(Integer, primary_key=True)
    bangumi_id = Column(Integer, unique=True, index=True)
    anilist_id = Column(Integer, unique=True, index=True)
    tmdb_id = Column(Integer)
    tmdb_season = Column(Integer, default=1)
    anidb_id = Column(Integer)
    imdb_id = Column(String)
    confidence = Column(Float)
    verified_by = Column(String, default="agent")  # agent/human
    mapping_data = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


class RSSSource(Base):
    """RSS feed source."""

    __tablename__ = "rss_sources"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    url = Column(String, nullable=False)
    parser_rules = Column(Text)
    is_active = Column(Boolean, default=True)


class AutoSubscribeRule(Base):
    """Rule for automatically subscribing to discovered seasonal anime."""

    __tablename__ = "auto_subscribe_rules"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    include_genres = Column(Text)  # comma-separated
    exclude_genres = Column(Text)
    include_formats = Column(Text)
    exclude_formats = Column(Text)
    include_keywords = Column(Text)
    exclude_keywords = Column(Text)
    min_score = Column(Float)
    use_llm = Column(Boolean, default=False)
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class SystemConfig(Base):
    """Key-value system config."""

    __tablename__ = "system_config"

    key = Column(String, primary_key=True)
    value = Column(Text)


class UserRequest(Base):
    """User request pending clarification or processing."""

    __tablename__ = "user_requests"

    id = Column(Integer, primary_key=True)
    request_type = Column(String, nullable=False)
    raw_input = Column(Text, nullable=False)
    parsed_title = Column(String)
    parsed_season = Column(Integer)
    parsed_episodes = Column(String)
    anilist_candidates = Column(Text)
    selected_anilist_id = Column(Integer)
    status = Column(String, default="pending")
    system_message = Column(Text)
    response_to_user = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class TaskSchedule(Base):
    """Scheduled task for subscription checks."""

    __tablename__ = "task_schedules"

    id = Column(Integer, primary_key=True)
    subscription_id = Column(Integer, ForeignKey("subscriptions.id"), unique=True)
    task_type = Column(String, default="check_updates")
    next_run_at = Column(DateTime, index=True)
    last_run_at = Column(DateTime)
    is_active = Column(Boolean, default=True)

    subscription = relationship("Subscription", back_populates="schedules")


class ErrorLog(Base):
    """Error handling log for Agent-driven error recovery."""

    __tablename__ = "error_logs"

    id = Column(Integer, primary_key=True)
    episode_id = Column(Integer, ForeignKey("episodes.id"), index=True)
    subscription_id = Column(Integer, index=True)
    node_name = Column(String, nullable=False)
    error_message = Column(Text)
    bash_commands_tried = Column(Text)  # JSON: [{"command": "...", "output": "...", "success": bool}]
    llm_reasoning = Column(Text)
    resolution = Column(String)  # "bash_fixed" / "retry_success" / "skip" / "exhausted"
    created_at = Column(DateTime, default=datetime.utcnow)

"""FastAPI web panel for AnimeAgent."""

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from fastapi import Depends, FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from anime_agent.config import settings
from anime_agent.memory.database import get_db
from anime_agent.memory.init_db import init_database
from anime_agent.memory.models import AutoSubscribeRule, Episode, RSSSource, Subscription
from anime_agent.memory.store import Store
from anime_agent.services.content_filter import ContentFilter, FilterRules
from anime_agent.services.metadata_resolver import MetadataResolver
from anime_agent.services.series_metadata_resolver import SeriesMetadataResolver
from anime_agent.tools.anilist_tool import AniListTool, AniListToolInput
from anime_agent.tools.bangumi_tool import BangumiTool, BangumiToolInput
from anime_agent.tools.base import BaseTool
from anime_agent.web_schemas import (
    AnimeLookupResponse,
    AutoSubscribeRuleCreateRequest,
    AutoSubscribeRuleResponse,
    AutoSubscribeRuleUpdateRequest,
    DiscoverySubscribeRequest,
    EpisodeDetailResponse,
    EpisodeResponse,
    HumanInputRequest,
    RSSSourceCreateRequest,
    RSSSourceResponse,
    RSSSourceUpdateRequest,
    SubscriptionCreateRequest,
    SubscriptionResponse,
    SubscriptionUpdateRequest,
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Initialize the database on application startup."""
    await init_database()
    yield


app = FastAPI(title="AnimeAgent", lifespan=lifespan)

# CORS: allow the Vite dev server and any same-origin production build.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def _create_subscription_from_payload(
    db: AsyncSession,
    payload: SubscriptionCreateRequest | DiscoverySubscribeRequest,
    source: str,
) -> Subscription:
    """Create a subscription, resolve metadata, create episodes and schedule."""
    store = Store(db)

    # Return existing subscription when the same external id is already tracked.
    if payload.bangumi_id is not None:
        existing = await store.subscriptions.get_by_bangumi_id(payload.bangumi_id)
        if existing is not None:
            return existing
    if payload.anilist_id is not None:
        existing = await store.subscriptions.get_by_anilist_id(payload.anilist_id)
        if existing is not None:
            return existing

    resolver = MetadataResolver()
    series_resolver = SeriesMetadataResolver()
    details: dict[str, Any] = {}

    if payload.bangumi_id or payload.anilist_id:
        try:
            result = await resolver.get_details(
                bangumi_id=payload.bangumi_id, anilist_id=payload.anilist_id
            )
            if result.success:
                details = result.data.get("details", {})
        except Exception as exc:  # noqa: BLE001
            # Metadata resolution is best-effort; payload values take precedence.
            logger.warning("Metadata resolution failed for subscription: {}", exc)
    elif payload.title_romaji and not payload.title_chinese:
        # No external IDs and no Chinese title — search by romaji title to fill metadata.
        try:
            search_result = await resolver.search(payload.title_romaji)
            if search_result.success and search_result.data.get("candidates"):
                details = search_result.data["candidates"][0]
        except Exception as exc:  # noqa: BLE001
            logger.warning("Title search metadata resolution failed: {}", exc)

    title_romaji = payload.title_romaji or details.get("title_romaji") or "Unknown"
    title_native = payload.title_native or details.get("title_native")
    title_chinese = payload.title_chinese or details.get("title_chinese")
    total_episodes = payload.total_episodes or details.get("total_episodes") or 12

    anime_for_series = {
        "title_chinese": title_chinese,
        "title_romaji": title_romaji,
        "title_native": title_native,
        "format": details.get("format") if details else None,
        "season": payload.season or details.get("season"),
        "season_year": payload.season_year or details.get("season_year"),
        "total_episodes": total_episodes,
    }
    series_meta = await series_resolver.resolve(anime_for_series)

    subscription = Subscription(
        bangumi_id=payload.bangumi_id or details.get("bangumi_id"),
        anilist_id=payload.anilist_id or details.get("anilist_id"),
        title_romaji=title_romaji,
        title_native=title_native,
        title_chinese=title_chinese,
        season_year=payload.season_year or details.get("season_year"),
        season=payload.season or details.get("season"),
        total_episodes=total_episodes or None,
        local_folder_name=series_meta.series_title,
        series_title=series_meta.series_title,
        season_number=series_meta.season_number,
        auto_download_enabled=True,
        fallback_to_resource_search=resolver.should_fallback_to_resource_search(
            details or {}, settings.resource_fallback_old_anime_days
        ),
        source=source,
        rss_source_id=getattr(payload, "rss_source_id", None),
    )
    db.add(subscription)
    await db.flush()

    for number in range(1, (total_episodes or 0) + 1):
        db.add(
            Episode(
                subscription_id=subscription.id,
                episode_number=number,
                status="pending",
            )
        )

    from anime_agent.memory.models import TaskSchedule

    # Schedule immediate check (next tick will process it within ~10 min)
    schedule = TaskSchedule(
        subscription_id=subscription.id,
        task_type="check_updates",
        next_run_at=datetime.now(UTC),
        is_active=True,
    )
    db.add(schedule)

    await db.commit()
    await db.refresh(subscription)
    return subscription


@app.get("/api/health")
async def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}


@app.get("/api/stats")
async def stats(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """Return aggregate counts for subscriptions and episodes."""
    sub_total = await db.scalar(select(func.count()).select_from(Subscription))
    sub_ongoing = await db.scalar(select(func.count()).where(Subscription.status == "ongoing"))
    sub_completed = await db.scalar(select(func.count()).where(Subscription.status == "completed"))

    ep_pending = await db.scalar(select(func.count()).where(Episode.status == "pending"))
    ep_completed = await db.scalar(select(func.count()).where(Episode.status == "completed"))
    ep_failed = await db.scalar(select(func.count()).where(Episode.status == "failed"))

    return {
        "subscriptions": {
            "total": sub_total or 0,
            "ongoing": sub_ongoing or 0,
            "completed": sub_completed or 0,
        },
        "episodes": {
            "pending": ep_pending or 0,
            "completed": ep_completed or 0,
            "failed": ep_failed or 0,
        },
    }


@app.get("/api/subscriptions")
async def list_subscriptions(db: AsyncSession = Depends(get_db)) -> list[dict[str, Any]]:
    """Return all subscriptions with episode progress stats in a single query."""
    downloaded_statuses = ("completed", "organized", "organized_with_warnings")
    stmt = (
        select(
            Subscription,
            func.count(Episode.id).label("ep_total"),
            func.count(Episode.id).filter(Episode.status == "completed").label("ep_completed"),
            func.count(Episode.id).filter(Episode.status.in_(downloaded_statuses)).label("ep_downloaded"),
            func.count(Episode.id).filter(Episode.status == "failed").label("ep_failed"),
            func.count(Episode.id).filter(Episode.status == "pending").label("ep_pending"),
        )
        .outerjoin(Episode, Subscription.id == Episode.subscription_id)
        .group_by(Subscription.id)
        .order_by(Subscription.created_at)
    )
    result = await db.execute(stmt)

    output: list[dict[str, Any]] = []
    for row in result.all():
        sub = row[0]
        sub_dict = {
            "id": sub.id,
            "bangumi_id": sub.bangumi_id,
            "anilist_id": sub.anilist_id,
            "title_romaji": sub.title_romaji,
            "title_native": sub.title_native,
            "title_chinese": sub.title_chinese,
            "season_year": sub.season_year,
            "season": sub.season,
            "total_episodes": sub.total_episodes,
            "local_folder_name": sub.local_folder_name,
            "status": sub.status,
            "source": sub.source,
            "auto_download_enabled": sub.auto_download_enabled,
            "expected_airing_weekday": sub.expected_airing_weekday,
            "expected_airing_time": sub.expected_airing_time,
            "airing_timezone": sub.airing_timezone,
            "created_at": sub.created_at.isoformat() if sub.created_at else None,
            "rss_source_id": sub.rss_source_id,
            "ep_total": row.ep_total or 0,
            "ep_completed": row.ep_completed or 0,
            "ep_downloaded": row.ep_downloaded or 0,
            "ep_failed": row.ep_failed or 0,
            "ep_pending": row.ep_pending or 0,
        }
        output.append(sub_dict)

    return output


@app.post("/api/subscriptions", response_model=SubscriptionResponse, status_code=201)
async def create_subscription(
    payload: SubscriptionCreateRequest, db: AsyncSession = Depends(get_db)
) -> Subscription:
    """Create a new manual subscription with metadata resolution and scheduling."""
    return await _create_subscription_from_payload(db, payload, source="manual")


@app.patch("/api/subscriptions/{subscription_id}", response_model=SubscriptionResponse)
async def update_subscription(
    subscription_id: int,
    payload: SubscriptionUpdateRequest,
    db: AsyncSession = Depends(get_db),
) -> Subscription:
    """Update a subscription's mutable fields."""
    subscription = await db.get(Subscription, subscription_id)
    if subscription is None:
        raise HTTPException(status_code=404, detail="Subscription not found")

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(subscription, field, value)

    await db.commit()
    await db.refresh(subscription)
    return subscription


@app.post("/api/subscriptions/{subscription_id}/refresh-metadata", response_model=SubscriptionResponse)
async def refresh_subscription_metadata(
    subscription_id: int, db: AsyncSession = Depends(get_db)
) -> Subscription:
    """Re-resolve metadata (Chinese title, etc.) for an existing subscription."""
    subscription = await db.get(Subscription, subscription_id)
    if subscription is None:
        raise HTTPException(status_code=404, detail="Subscription not found")

    resolver = MetadataResolver()
    details: dict[str, Any] = {}

    try:
        bangumi_id = cast(int | None, subscription.bangumi_id)
        anilist_id = cast(int | None, subscription.anilist_id)
        title_romaji = cast(str | None, subscription.title_romaji)
        if bangumi_id or anilist_id:
            result = await resolver.get_details(
                bangumi_id=bangumi_id, anilist_id=anilist_id
            )
            if result.success:
                details = result.data.get("details", {})
        elif title_romaji:
            search_result = await resolver.search(title_romaji)
            if search_result.success and search_result.data.get("candidates"):
                details = search_result.data["candidates"][0]
    except Exception as exc:  # noqa: BLE001
        logger.warning("Metadata refresh failed for subscription {}: {}", subscription_id, exc)

    if details:
        if details.get("title_chinese") and not subscription.title_chinese:
            subscription.title_chinese = details["title_chinese"]
        if details.get("title_native") and not subscription.title_native:
            subscription.title_native = details["title_native"]
        if details.get("bangumi_id") and not subscription.bangumi_id:
            subscription.bangumi_id = details["bangumi_id"]
        if details.get("anilist_id") and not subscription.anilist_id:
            subscription.anilist_id = details["anilist_id"]
        if details.get("total_episodes") and not subscription.total_episodes:
            subscription.total_episodes = details["total_episodes"]
        # Update local folder name if we got a Chinese title
        if subscription.title_chinese:
            subscription.local_folder_name = subscription.title_chinese

        await db.commit()
        await db.refresh(subscription)

    return subscription


@app.delete("/api/subscriptions/{subscription_id}", status_code=204)
async def delete_subscription(subscription_id: int, db: AsyncSession = Depends(get_db)) -> Response:
    """Delete a subscription and its associated episodes/schedules."""
    subscription = await db.get(Subscription, subscription_id)
    if subscription is None:
        raise HTTPException(status_code=404, detail="Subscription not found")

    await db.delete(subscription)
    await db.commit()
    return Response(status_code=204)


@app.get("/api/episodes", response_model=list[EpisodeResponse])
async def list_episodes(
    subscription_id: int | None = None,
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    """Return episodes with subscription title, optionally filtered.

    ``status`` accepts a comma-separated list to allow multi-select filtering.
    """
    query = select(Episode).order_by(Episode.subscription_id, Episode.episode_number)
    if subscription_id is not None:
        query = query.where(Episode.subscription_id == subscription_id)
    if status:
        statuses = [s.strip() for s in status.split(",") if s.strip()]
        if len(statuses) == 1:
            query = query.where(Episode.status == statuses[0])
        elif statuses:
            query = query.where(Episode.status.in_(statuses))

    result = await db.execute(query)
    episodes = list(result.scalars().all())

    # Batch-load subscription titles
    sub_ids = {cast(int, ep.subscription_id) for ep in episodes}
    subs: dict[int, Subscription] = {}
    if sub_ids:
        sub_result = await db.execute(
            select(Subscription).where(Subscription.id.in_(sub_ids))
        )
        subs = {cast(int, s.id): s for s in sub_result.scalars().all()}

    output: list[dict[str, Any]] = []
    for ep in episodes:
        sub = subs.get(cast(int, ep.subscription_id))
        candidates = []
        if ep.torrent_candidates:
            try:
                import json
                candidates = json.loads(cast(str, ep.torrent_candidates))
            except json.JSONDecodeError:
                pass
        output.append({
            "id": ep.id,
            "subscription_id": ep.subscription_id,
            "subscription_title": sub.title_chinese or sub.title_native or sub.title_romaji if sub else None,
            "episode_number": ep.episode_number,
            "title": ep.title,
            "aired_at": ep.aired_at.isoformat() if ep.aired_at else None,
            "status": ep.status,
            "content_type": ep.content_type,
            "torrent_hash": ep.torrent_hash,
            "torrent_info_hash": ep.torrent_info_hash,
            "torrent_title": ep.torrent_title,
            "torrent_name": ep.torrent_name,
            "torrent_link": ep.torrent_link,
            "torrent_status": ep.torrent_status,
            "torrent_last_speed": ep.torrent_last_speed or 0.0,
            "torrent_progress": ep.torrent_progress or 0.0,
            "torrent_added_at": ep.torrent_added_at.isoformat() if ep.torrent_added_at else None,
            "torrent_checked_at": ep.torrent_checked_at.isoformat() if ep.torrent_checked_at else None,
            "download_path": ep.download_path,
            "organized_path": ep.organized_path,
            "metadata_verified": ep.metadata_verified,
            "error_log": ep.error_log,
            "torrent_candidates_count": len(candidates),
            "created_at": ep.created_at.isoformat() if ep.created_at else None,
            "updated_at": ep.updated_at.isoformat() if ep.updated_at else None,
        })

    return output


@app.get("/api/episodes/{episode_id}", response_model=EpisodeDetailResponse)
async def get_episode_detail(episode_id: int, db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """Return full details for a single episode."""
    episode = await db.get(Episode, episode_id)
    if episode is None:
        raise HTTPException(status_code=404, detail="Episode not found")

    sub = await db.get(Subscription, cast(int, episode.subscription_id))
    subscription_title = sub.title_chinese or sub.title_native or sub.title_romaji if sub else None

    candidates: list[dict[str, Any]] = []
    if episode.torrent_candidates:
        try:
            import json
            candidates = json.loads(cast(str, episode.torrent_candidates))
        except json.JSONDecodeError:
            pass

    failed_hashes: list[str] = []
    if episode.torrent_failed_hashes:
        try:
            import json
            failed_hashes = json.loads(cast(str, episode.torrent_failed_hashes))
        except json.JSONDecodeError:
            pass

    return {
        "id": episode.id,
        "subscription_id": episode.subscription_id,
        "subscription_title": subscription_title,
        "episode_number": episode.episode_number,
        "title": episode.title,
        "aired_at": episode.aired_at.isoformat() if episode.aired_at else None,
        "status": episode.status,
        "content_type": episode.content_type,
        "torrent_hash": episode.torrent_hash,
        "torrent_info_hash": episode.torrent_info_hash,
        "torrent_title": episode.torrent_title,
        "torrent_name": episode.torrent_name,
        "torrent_link": episode.torrent_link,
        "torrent_status": episode.torrent_status,
        "torrent_last_speed": episode.torrent_last_speed or 0.0,
        "torrent_progress": episode.torrent_progress or 0.0,
        "torrent_added_at": episode.torrent_added_at.isoformat() if episode.torrent_added_at else None,
        "torrent_checked_at": episode.torrent_checked_at.isoformat() if episode.torrent_checked_at else None,
        "download_path": episode.download_path,
        "organized_path": episode.organized_path,
        "metadata_verified": episode.metadata_verified,
        "error_log": episode.error_log,
        "torrent_candidates_count": len(candidates),
        "torrent_candidates": candidates,
        "torrent_failed_hashes": failed_hashes,
        "created_at": episode.created_at.isoformat() if episode.created_at else None,
        "updated_at": episode.updated_at.isoformat() if episode.updated_at else None,
    }


@app.post("/api/episodes/{episode_id}/retry", response_model=EpisodeResponse)
async def retry_episode(episode_id: int, db: AsyncSession = Depends(get_db)) -> Episode:
    """Reset a failed episode to pending so it can be retried."""
    episode = await db.get(Episode, episode_id)
    if episode is None:
        raise HTTPException(status_code=404, detail="Episode not found")

    episode.status = "pending"  # type: ignore[assignment]
    episode.error_log = ""  # type: ignore[assignment]
    episode.torrent_candidates_attempt_count = 0  # type: ignore[assignment]
    episode.low_confidence_count = 0  # type: ignore[assignment]
    episode.torrent_failed_hashes = "[]"  # type: ignore[assignment]

    await db.commit()
    await db.refresh(episode)
    return episode


@app.post("/api/episodes/{episode_id}/human_input", response_model=EpisodeResponse)
async def submit_human_input(
    episode_id: int,
    payload: HumanInputRequest,
    db: AsyncSession = Depends(get_db),
) -> Episode:
    """Provide human approval for a low-confidence torrent match."""
    episode = await db.get(Episode, episode_id)
    if episode is None:
        raise HTTPException(status_code=404, detail="Episode not found")

    if episode.status != "human_review":
        raise HTTPException(status_code=409, detail="Episode is not awaiting human review")

    episode.human_input = payload.action  # type: ignore[assignment]

    if payload.action == "approve":
        episode.status = "matched"  # type: ignore[assignment]
        if payload.torrent_link:
            episode.torrent_title = payload.torrent_link  # type: ignore[assignment]
    else:
        episode.status = "pending"  # type: ignore[assignment]
        episode.low_confidence_count = 0  # type: ignore[assignment]

    await db.commit()
    await db.refresh(episode)
    return episode


@app.get("/api/anime/lookup", response_model=AnimeLookupResponse)
async def anime_lookup(
    source: str,
    id: int,  # noqa: A002
) -> AnimeLookupResponse:
    """Look up anime metadata by Bangumi or AniList ID."""
    if source == "bangumi":
        tool = BangumiTool()
        result = await tool.invoke(BangumiToolInput(action="details", subject_id=id))
        if not result.success:
            raise HTTPException(status_code=502, detail=result.error)
        subject = result.data.get("subject", {})
        return AnimeLookupResponse(
            bangumi_id=subject.get("bangumi_id"),
            title_romaji=subject.get("title_romaji"),
            title_native=subject.get("title_native"),
            title_chinese=subject.get("title_chinese"),
            title_english=subject.get("title_english"),
            format=subject.get("format"),
            total_episodes=subject.get("total_episodes"),
            season=subject.get("season"),
            season_year=subject.get("season_year"),
        )
    if source == "anilist":
        tool = AniListTool()
        result = await tool.invoke(AniListToolInput(action="details", media_id=id))
        if not result.success:
            raise HTTPException(status_code=502, detail=result.error)
        media = result.data.get("media", {})
        return AnimeLookupResponse(
            anilist_id=media.get("anilist_id"),
            title_romaji=media.get("title_romaji"),
            title_native=media.get("title_native"),
            title_english=media.get("title_english"),
            format=media.get("format"),
            total_episodes=media.get("total_episodes"),
            season=media.get("season"),
            season_year=media.get("season_year"),
        )
    raise HTTPException(status_code=400, detail=f"Unsupported source: {source}")


@app.get("/api/discovery/season")
async def discovery_season(
    year: int,
    season: str,
    apply_filters: bool = True,
    search: str | None = None,
) -> list[dict[str, Any]]:
    """Return seasonal anime, using Bangumi (Chinese titles) as primary source."""
    resolver = MetadataResolver()
    result = await resolver.get_seasonal(year, season.upper())
    if not result.success:
        raise HTTPException(status_code=502, detail=result.error)

    media = cast(list[dict[str, Any]], result.data.get("candidates", []))

    if search:
        s = search.lower()
        media = [
            anime
            for anime in media
            if s in (anime.get("title_chinese") or "").lower()
            or s in (anime.get("title_native") or "").lower()
            or s in (anime.get("title_romaji") or "").lower()
            or s in (anime.get("title_english") or "").lower()
        ]

    # Best-effort enrichment: if we fell back to AniList, try to backfill
    # Chinese titles and bangumi_id from Bangumi search.
    if result.data.get("source") == "anilist":
        bgm = BangumiTool()
        sem = asyncio.Semaphore(5)

        async def _search_bgm(anime: dict[str, Any]) -> None:
            if anime.get("title_chinese") and anime.get("bangumi_id"):
                return
            query = anime.get("title_native") or anime.get("title_romaji") or ""
            if not query:
                return
            async with sem:
                try:
                    search_result = await bgm.invoke(BangumiToolInput(action="search", query=query))
                    if search_result.success and search_result.data.get("subjects"):
                        best = search_result.data["subjects"][0]
                        anime.setdefault("title_chinese", best.get("title_chinese"))
                        anime.setdefault("bangumi_id", best.get("bangumi_id"))
                except Exception:  # noqa: BLE001
                    pass  # best-effort

        await asyncio.gather(*[_search_bgm(a) for a in media])

    if not apply_filters:
        return media

    rules = FilterRules(
        exclude_ova=settings.filter_exclude_ova,
        exclude_movies=settings.filter_exclude_movies,
        min_duration_minutes=settings.filter_min_duration_minutes,
        exclude_genres=settings.filter_exclude_genres,
        exclude_formats=settings.filter_exclude_formats,
        require_anime_type=settings.filter_require_anime_type,
    )
    content_filter = ContentFilter(rules)

    filtered = []
    for anime in media:
        filter_result = content_filter.apply(anime)
        anime["filtered"] = not filter_result.allowed
        anime["filter_reason"] = filter_result.reason
        filtered.append(anime)

    return filtered


@app.get("/api/logs")
async def logs(limit: int = 100) -> list[str]:
    """Return the most recent lines from the log file."""
    log_path = Path("logs/anime_agent.log")
    if not log_path.exists():
        return []

    text = log_path.read_text(encoding="utf-8")
    lines = [line for line in text.splitlines() if line]
    return lines[-limit:]


@app.get("/api/tools/health")
async def tools_health() -> dict[str, dict[str, Any]]:
    """Return the health status of all integrated external tools."""
    from anime_agent.tools.anilist_tool import AniListTool
    from anime_agent.tools.bangumi_tool import BangumiTool
    from anime_agent.tools.emby_tool import EmbyTool
    from anime_agent.tools.qb_tool import QBTool
    from anime_agent.tools.rss_tool import RSSTool
    from anime_agent.tools.tmdb_tool import TMDBTool

    tools: list[tuple[str, BaseTool]] = [
        ("bangumi", BangumiTool()),
        ("anilist", AniListTool()),
        ("tmdb", TMDBTool(api_key=settings.tmdb_api_key)),
        ("rss", RSSTool()),
        ("qbittorrent", QBTool()),
        ("emby", EmbyTool()),
    ]

    results: dict[str, dict[str, Any]] = {}
    for name, tool in tools:
        try:
            result = await tool.healthcheck()
            results[name] = {"healthy": result.success, "detail": result.error or "ok"}
        except Exception as exc:  # noqa: BLE001
            results[name] = {"healthy": False, "detail": str(exc)}

    return results


@app.post("/api/discovery/subscribe", response_model=SubscriptionResponse, status_code=201)
async def discovery_subscribe(
    payload: DiscoverySubscribeRequest, db: AsyncSession = Depends(get_db)
) -> Subscription:
    """Subscribe to an anime discovered on the discovery page with scheduling."""
    return await _create_subscription_from_payload(db, payload, source="auto_discover")


@app.get("/api/rss-sources", response_model=list[RSSSourceResponse])
async def list_rss_sources(db: AsyncSession = Depends(get_db)) -> list[RSSSource]:
    """Return all RSS sources ordered by name."""
    store = Store(db)
    return await store.rss_sources.list_all()


@app.post("/api/rss-sources", response_model=RSSSourceResponse, status_code=201)
async def create_rss_source(
    payload: RSSSourceCreateRequest, db: AsyncSession = Depends(get_db)
) -> RSSSource:
    """Create a new RSS source."""
    store = Store(db)
    source = RSSSource(
        name=payload.name,
        url=payload.url,
        parser_rules=payload.parser_rules,
        is_active=payload.is_active,
    )
    return await store.rss_sources.create(source)


@app.patch("/api/rss-sources/{source_id}", response_model=RSSSourceResponse)
async def update_rss_source(
    source_id: int, payload: RSSSourceUpdateRequest, db: AsyncSession = Depends(get_db)
) -> RSSSource:
    """Update an RSS source."""
    store = Store(db)
    source = await store.rss_sources.get_by_id(source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="RSS source not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(source, field, value)

    return await store.rss_sources.update(source)


@app.delete("/api/rss-sources/{source_id}", status_code=204)
async def delete_rss_source(source_id: int, db: AsyncSession = Depends(get_db)) -> Response:
    """Delete an RSS source."""
    store = Store(db)
    source = await store.rss_sources.get_by_id(source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="RSS source not found")

    await store.rss_sources.delete(source)
    return Response(status_code=204)


@app.get("/api/auto-subscribe-rules", response_model=list[AutoSubscribeRuleResponse])
async def list_auto_subscribe_rules(db: AsyncSession = Depends(get_db)) -> list[AutoSubscribeRule]:
    """Return all auto-subscribe rules."""
    store = Store(db)
    return await store.auto_subscribe_rules.list_all()


@app.post("/api/auto-subscribe-rules", response_model=AutoSubscribeRuleResponse, status_code=201)
async def create_auto_subscribe_rule(
    payload: AutoSubscribeRuleCreateRequest, db: AsyncSession = Depends(get_db)
) -> AutoSubscribeRule:
    """Create a new auto-subscribe rule."""
    store = Store(db)
    rule = AutoSubscribeRule(**payload.model_dump())
    return await store.auto_subscribe_rules.create(rule)


@app.patch("/api/auto-subscribe-rules/{rule_id}", response_model=AutoSubscribeRuleResponse)
async def update_auto_subscribe_rule(
    rule_id: int,
    payload: AutoSubscribeRuleUpdateRequest,
    db: AsyncSession = Depends(get_db),
) -> AutoSubscribeRule:
    """Update an auto-subscribe rule."""
    store = Store(db)
    rule = await store.auto_subscribe_rules.get_by_id(rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="Rule not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(rule, field, value)

    return await store.auto_subscribe_rules.update(rule)


@app.delete("/api/auto-subscribe-rules/{rule_id}", status_code=204)
async def delete_auto_subscribe_rule(rule_id: int, db: AsyncSession = Depends(get_db)) -> Response:
    """Delete an auto-subscribe rule."""
    store = Store(db)
    rule = await store.auto_subscribe_rules.get_by_id(rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="Rule not found")

    await store.auto_subscribe_rules.delete(rule)
    return Response(status_code=204)


_frontend_dist = Path(__file__).parent.parent / "frontend" / "dist"
if _frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(_frontend_dist), html=True), name="frontend")

"""End-to-end Episode Graph test with real RSS fixture and fake download/Emby."""

from pathlib import Path
from typing import Any

import pytest
import respx
from httpx import Response
from sqlalchemy.ext.asyncio import AsyncSession

from anime_agent.agents.episode.graph import build_episode_graph
from anime_agent.agents.episode.nodes.fetch_rss import FetchRSSNode
from anime_agent.agents.episode.nodes.match_torrent import MatchTorrentNode
from anime_agent.agents.episode.nodes.organize_files import OrganizeFilesNode
from anime_agent.agents.episode.nodes.poll_download import PollDownloadNode
from anime_agent.agents.episode.nodes.refresh_emby import RefreshEmbyNode
from anime_agent.agents.episode.nodes.send_download import SendDownloadNode
from anime_agent.agents.episode.runner import EpisodeGraphRunner
from anime_agent.memory.models import Episode, RSSSource, Subscription
from anime_agent.memory.store import Store
from anime_agent.services.torrent_selector import TorrentSelector
from anime_agent.tools.base import ToolOutput
from anime_agent.tools.rss_tool import RSSTool
from sqlalchemy.ext.asyncio import async_sessionmaker
from tests.fakes import FakeEmbyTool, FakeFileSystemTool, FakeQBTool


@pytest.fixture
def animes_garden_feed() -> str:
    """Return the real Anime Garden RSS fixture as text."""
    fixture_path = Path(__file__).parent.parent / "test_tools" / "fixtures" / "animes_garden_feed.xml"
    return fixture_path.read_text(encoding="utf-8")


@pytest.fixture
async def pipeline_subscription(db_session: AsyncSession) -> Subscription:
    """Create a subscription and episode for the pipeline test."""
    store = Store(db_session)
    source = RSSSource(name="Anime Garden", url="https://api.animes.garden/feed.xml", is_active=True)
    await store.rss_sources.create(source)

    subscription = Subscription(
        bangumi_id=160209,
        title_romaji="ReZero kara Hajimeru Isekai Seikatsu",
        title_chinese="Re：从零开始的异世界生活",
        total_episodes=1,
        local_folder_name="ReZero",
        status="ongoing",
        source="manual",
        auto_download_enabled=True,
        rss_source_id=source.id,
    )
    await store.subscriptions.create(subscription)

    episode = Episode(
        subscription_id=subscription.id,
        episode_number=1,
        status="pending",
    )
    await store.episodes.create(episode)

    return subscription


@pytest.mark.real_data
@respx.mock
async def test_episode_pipeline_with_real_rss_fixture(
    db_session: AsyncSession,
    pipeline_subscription: Subscription,
    animes_garden_feed: str,
    tmp_path: Path,
) -> None:
    """Run the full Episode Graph against a real RSS fixture and fake downstream tools."""
    respx.get("https://api.animes.garden/feed.xml").mock(
        return_value=Response(200, text=animes_garden_feed)
    )

    downloads_dir = tmp_path / "downloads"
    fake_qb = FakeQBTool(complete_after_calls=1, download_root=downloads_dir)
    fake_emby = FakeEmbyTool()
    fake_fs = FakeFileSystemTool(library_path=str(tmp_path / "library"))

    class HighConfidenceMatchTorrentNode(MatchTorrentNode):
        def __init__(self) -> None:
            # Use a fake selector to avoid requiring a real LLM API key.
            self.selector = _FakeSelector()

    class _FakeSelector:
        async def select(
            self,
            candidates: list[dict[str, Any]],
            episode_number: int,
            title_variants: list[str],
            failed_hashes: list[str],
        ) -> ToolOutput:
            for candidate in candidates:
                if candidate.get("info_hash") and candidate.get("info_hash") not in failed_hashes:
                    return ToolOutput(
                        success=True,
                        data={
                            "matched": True,
                            "info_hash": candidate["info_hash"],
                            "title": candidate.get("title", ""),
                            "link": candidate.get("link", ""),
                            "confidence": 0.95,
                        },
                    )
            return ToolOutput(success=True, data={"matched": False})

    # Use a real session factory so FetchRSSNode can open/close its own sessions
    # without closing the test fixture's db_session.
    session_factory = async_sessionmaker(
        bind=db_session.bind, expire_on_commit=False
    )

    graph = build_episode_graph(
        fetch_rss=FetchRSSNode(rss_tool=RSSTool(), session_factory=session_factory),
        match_torrent=HighConfidenceMatchTorrentNode(),
        send_download=SendDownloadNode(qb_tool=fake_qb),
        poll_download=PollDownloadNode(qb_tool=fake_qb),
        organize_files=OrganizeFilesNode(
            fs_tool=fake_fs,
            library_path=str(tmp_path / "library"),
        ),
        refresh_emby=RefreshEmbyNode(emby_tool=fake_emby),
    )

    runner = EpisodeGraphRunner(session_factory=lambda: db_session, graph=graph)
    final = await runner.run(
        subscription_id=pipeline_subscription.id,
        episode_number=1,
        session=db_session,
    )

    assert final["status"] == "completed"
    assert final["emby_refreshed"] is True
    assert len(fake_emby.refreshes) == 1

    store = Store(db_session)
    episode = await store.episodes.get_by_subscription_and_number(
        pipeline_subscription.id, 1
    )
    assert episode is not None
    assert episode.status == "completed"
    assert episode.torrent_hash is not None
    assert episode.organized_path is not None

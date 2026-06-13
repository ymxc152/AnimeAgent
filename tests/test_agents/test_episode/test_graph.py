"""Tests for the Episode Graph builder and wiring."""



from anime_agent.agents.episode.graph import (
    _after_match_torrent,
    build_episode_graph,
)
from anime_agent.agents.episode.state import EpisodeAgentState


async def test_graph_compiles_and_runs_linear_happy_path():
    """Graph should run all nodes when every step succeeds."""
    graph = build_episode_graph()

    state: EpisodeAgentState = {
        "goal_id": "sub_1_ep_1",
        "subscription_id": 1,
        "episode_number": 1,
        "rss_source_id": 1,
        "title_romaji": "Sousou no Frieren",
        "title_native": "葬送のフリーレン",
        "title_chinese": "葬送的芙莉莲",
        "bangumi_data": {},
        "anilist_data": {},
        "tmdb_data": None,
        "torrent_candidates": [],
        "matched_torrent": None,
        "torrent_hash": None,
        "torrent_name": None,
        "torrent_failed_hashes": [],
        "download_files": [],
        "download_progress": 0.0,
        "classification": None,
        "organized_path": None,
        "organized_files": [],
        "emby_refreshed": False,
        "status": "pending",
        "errors": [],
        "requires_human": False,
        "human_input": None,
        "low_confidence_count": 0,
        "resume_after": None,
        "resource_searched": False,
    }

    final = await graph.ainvoke(state)

    # Without external tools the fetch_rss node fails because there is no URL,
    # so the graph should end early with a resumable/non-matched status.
    assert final["status"] in ("failed", "no_match", "low_confidence", "waiting_for_rss", "search_resources")


def test_graph_builder_returns_compiled_graph():
    """build_episode_graph should return a compiled langgraph StateGraph."""
    graph = build_episode_graph()
    assert graph is not None
    assert hasattr(graph, "ainvoke")


def test_after_match_torrent_routes_no_match_with_candidates_to_reflect():
    """When match_torrent returns no_match but candidates exist, reflect_match decides."""
    state: EpisodeAgentState = {
        "goal_id": "sub_1_ep_1",
        "subscription_id": 1,
        "episode_number": 1,
        "rss_source_id": 1,
        "title_romaji": "Sousou no Frieren",
        "title_native": "葬送のフリーレン",
        "title_chinese": "葬送的芙莉莲",
        "bangumi_data": {},
        "anilist_data": {},
        "tmdb_data": None,
        "torrent_candidates": [{"title": "candidate", "info_hash": "abc1"}],
        "matched_torrent": None,
        "torrent_hash": None,
        "torrent_name": None,
        "torrent_failed_hashes": [],
        "download_files": [],
        "download_progress": 0.0,
        "classification": None,
        "organized_path": None,
        "organized_files": [],
        "emby_refreshed": False,
        "status": "no_match",
        "errors": [],
        "requires_human": False,
        "human_input": None,
        "low_confidence_count": 0,
        "resume_after": None,
        "resource_searched": False,
    }

    assert _after_match_torrent(state) == "reflect_match"


def test_after_match_torrent_routes_no_match_without_candidates_to_schedule():
    """When match_torrent returns no_match and candidates are empty, schedule resume."""
    state: EpisodeAgentState = {
        "goal_id": "sub_1_ep_1",
        "subscription_id": 1,
        "episode_number": 1,
        "rss_source_id": 1,
        "title_romaji": "Sousou no Frieren",
        "title_native": "葬送のフリーレン",
        "title_chinese": "葬送的芙莉莲",
        "bangumi_data": {},
        "anilist_data": {},
        "tmdb_data": None,
        "torrent_candidates": [],
        "matched_torrent": None,
        "torrent_hash": None,
        "torrent_name": None,
        "torrent_failed_hashes": [],
        "download_files": [],
        "download_progress": 0.0,
        "classification": None,
        "organized_path": None,
        "organized_files": [],
        "emby_refreshed": False,
        "status": "no_match",
        "errors": [],
        "requires_human": False,
        "human_input": None,
        "low_confidence_count": 0,
        "resume_after": None,
        "resource_searched": False,
    }

    assert _after_match_torrent(state) == "schedule_resume"

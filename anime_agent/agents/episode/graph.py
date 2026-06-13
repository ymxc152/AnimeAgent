"""Episode Graph definition."""

from typing import Any

from langgraph.graph import END, START
from langgraph.graph.state import CompiledStateGraph, StateGraph

from anime_agent.agents.episode.nodes.fetch_rss import FetchRSSNode
from anime_agent.agents.episode.nodes.handle_error import HandleErrorNode
from anime_agent.agents.episode.nodes.human_review import HumanReviewNode
from anime_agent.agents.episode.nodes.match_torrent import MatchTorrentNode
from anime_agent.agents.episode.nodes.organize_files import OrganizeFilesNode
from anime_agent.agents.episode.nodes.poll_download import PollDownloadNode
from anime_agent.agents.episode.nodes.reflect_match import ReflectMatchNode
from anime_agent.agents.episode.nodes.refresh_emby import RefreshEmbyNode
from anime_agent.agents.episode.nodes.schedule_resume import ScheduleResumeNode
from anime_agent.agents.episode.nodes.search_resources import SearchResourcesNode
from anime_agent.agents.episode.nodes.send_download import SendDownloadNode
from anime_agent.agents.episode.state import EpisodeAgentState


def _status_router(state: EpisodeAgentState) -> str:
    """Route a resumed graph to the node matching its current status."""
    status = state.get("status", "pending")
    return {
        "pending": "fetch_rss",
        "fetching": "fetch_rss",
        "matched": "send_download",
        "downloading": "poll_download",
        "downloaded": "organize_files",
        "organized": "refresh_emby",
        "organized_with_warnings": "refresh_emby",
        "human_review": "human_review",
        "failed": "handle_error",
    }.get(status, "fetch_rss")


def _after_fetch_rss(state: EpisodeAgentState) -> str:
    status = state.get("status")
    if status == "failed":
        return "handle_error"
    return "match_torrent"


def _after_match_torrent(state: EpisodeAgentState) -> str:
    status = state.get("status")
    if status == "matched":
        return "send_download"
    if status == "search_resources":
        return "search_resources"
    if status in ("waiting_for_rss", "no_match"):
        return "schedule_resume"
    if status == "low_confidence":
        return "reflect_match"
    return "handle_error"


def _after_reflect_match(state: EpisodeAgentState) -> str:
    status = state.get("status")
    if status == "matched":
        return "send_download"
    if status == "search_resources":
        return "search_resources"
    if status == "schedule_resume":
        return "schedule_resume"
    if status == "human_review":
        return "human_review"
    return "handle_error"


def _after_search_resources(state: EpisodeAgentState) -> str:
    status = state.get("status")
    if status == "searched":
        return "match_torrent"
    if status == "failed":
        return "schedule_resume"
    return "handle_error"


def _after_send_download(state: EpisodeAgentState) -> str:
    status = state.get("status")
    if status == "downloading":
        return "poll_download"
    return "handle_error"


def _after_poll_download(state: EpisodeAgentState) -> str:
    status = state.get("status")
    if status == "downloading":
        return "schedule_resume"
    if status == "downloaded":
        return "organize_files"
    if status == "retry_match":
        return "match_torrent"
    return "handle_error"


def _after_organize_files(state: EpisodeAgentState) -> str:
    status = state.get("status")
    if status in ("organized", "organized_with_warnings"):
        return "refresh_emby"
    return "handle_error"


def _after_refresh_emby(state: EpisodeAgentState) -> str:
    status = state.get("status")
    if status == "completed":
        return END
    return "handle_error"


def _after_human_review(state: EpisodeAgentState) -> str:
    status = state.get("status")
    if status == "matched":
        return "send_download"
    return END


def build_episode_graph(**node_overrides: Any) -> CompiledStateGraph:
    """Build and return the Episode Graph.

    Keyword arguments can be used to inject test doubles for any node.
    Accepts ``session_factory`` to pass to FetchRSSNode so it can query
    all active RSS sources from the database.
    """
    session_factory = node_overrides.pop("session_factory", None)
    builder = StateGraph(EpisodeAgentState)

    builder.add_node(
        "fetch_rss",
        node_overrides.get("fetch_rss", FetchRSSNode(session_factory=session_factory)),
    )
    builder.add_node("match_torrent", node_overrides.get("match_torrent", MatchTorrentNode()))
    builder.add_node("search_resources", node_overrides.get("search_resources", SearchResourcesNode()))
    builder.add_node("send_download", node_overrides.get("send_download", SendDownloadNode()))
    builder.add_node("poll_download", node_overrides.get("poll_download", PollDownloadNode()))
    builder.add_node("organize_files", node_overrides.get("organize_files", OrganizeFilesNode()))
    builder.add_node("refresh_emby", node_overrides.get("refresh_emby", RefreshEmbyNode()))
    builder.add_node("human_review", node_overrides.get("human_review", HumanReviewNode()))
    builder.add_node("reflect_match", node_overrides.get("reflect_match", ReflectMatchNode()))
    builder.add_node("schedule_resume", node_overrides.get("schedule_resume", ScheduleResumeNode()))
    builder.add_node("handle_error", node_overrides.get("handle_error", HandleErrorNode()))

    builder.add_conditional_edges(START, _status_router)

    builder.add_conditional_edges("fetch_rss", _after_fetch_rss)
    builder.add_conditional_edges("match_torrent", _after_match_torrent)
    builder.add_conditional_edges("reflect_match", _after_reflect_match)
    builder.add_conditional_edges("search_resources", _after_search_resources)
    builder.add_conditional_edges("send_download", _after_send_download)
    builder.add_conditional_edges("poll_download", _after_poll_download)
    builder.add_conditional_edges("organize_files", _after_organize_files)
    builder.add_conditional_edges("refresh_emby", _after_refresh_emby)
    builder.add_conditional_edges("human_review", _after_human_review)
    builder.add_edge("schedule_resume", END)
    builder.add_edge("handle_error", END)

    return builder.compile()

"""Episode Graph definition."""

from typing import Any

from langgraph.graph import END, START
from langgraph.graph.state import CompiledStateGraph, StateGraph

from anime_agent.agents.episode.error_handler import ErrorHandlerNode
from anime_agent.agents.episode.nodes.fetch_rss import FetchRSSNode
from anime_agent.agents.episode.nodes.handle_error import HandleErrorNode
from anime_agent.agents.episode.nodes.human_review import HumanReviewNode
from anime_agent.agents.episode.nodes.match_torrent import MatchTorrentNode
from anime_agent.agents.episode.nodes.notify_user import NotifyUserNode
from anime_agent.agents.episode.nodes.organize_files import OrganizeFilesNode
from anime_agent.agents.episode.nodes.poll_download import PollDownloadNode
from anime_agent.agents.episode.nodes.process_metadata import ProcessMetadataNode
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
        "downloaded": "process_metadata",
        "metadata_processed": "organize_files",
        "organized": "refresh_emby",
        "organized_with_warnings": "refresh_emby",
        "human_review": "human_review",
        "failed": "error_handler",
    }.get(status, "fetch_rss")


def _after_fetch_rss(state: EpisodeAgentState) -> str:
    status = state.get("status")
    if status == "failed":
        return "error_handler"
    return "match_torrent"


def _after_match_torrent(state: EpisodeAgentState) -> str:
    status = state.get("status")
    if status == "matched":
        return "send_download"
    if status == "search_resources":
        return "search_resources"
    if status == "waiting_for_rss":
        return "schedule_resume"
    if status == "low_confidence":
        return "reflect_match"
    if status == "no_match":
        # If we have candidates but the matcher couldn't decide, let the
        # reflection agent choose between searching elsewhere or giving up.
        if state.get("torrent_candidates"):
            return "reflect_match"
        return "schedule_resume"
    return "error_handler"


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
    return "error_handler"


def _after_search_resources(state: EpisodeAgentState) -> str:
    status = state.get("status")
    if status == "searched":
        return "match_torrent"
    if status == "failed":
        return "schedule_resume"
    return "error_handler"


def _after_send_download(state: EpisodeAgentState) -> str:
    status = state.get("status")
    if status == "downloading":
        return "poll_download"
    if status == "retry_match":
        # send_download failed (qB error, duplicate hash, bad link, etc.)
        # Let the matcher pick another candidate, excluding the failed hash.
        return "match_torrent"
    return "error_handler"


def _after_poll_download(state: EpisodeAgentState) -> str:
    status = state.get("status")
    if status == "downloading":
        return "schedule_resume"
    if status == "downloaded":
        return "process_metadata"
    if status == "retry_match":
        return "match_torrent"
    return "error_handler"


def _after_process_metadata(state: EpisodeAgentState) -> str:
    status = state.get("status")
    if status == "metadata_processed":
        return "organize_files"
    return "error_handler"


def _after_organize_files(state: EpisodeAgentState) -> str:
    status = state.get("status")
    if status in ("organized", "organized_with_warnings"):
        return "refresh_emby"
    return "error_handler"


def _after_refresh_emby(state: EpisodeAgentState) -> str:
    status = state.get("status")
    if status == "completed":
        return "notify_user"
    return "error_handler"


def _after_error_handler(state: EpisodeAgentState) -> str:
    """Route after ErrorHandler completes its attempt."""
    status = state.get("status", "failed")
    if status.startswith("retry_"):
        # retry_organize_files -> organize_files, retry_send_download -> send_download, etc.
        target = status.replace("retry_", "")
        # Map to valid node names
        valid_nodes = {
            "fetch_rss",
            "match_torrent",
            "search_resources",
            "send_download",
            "poll_download",
            "process_metadata",
            "organize_files",
            "refresh_emby",
        }
        return target if target in valid_nodes else "handle_error"
    if status == "skipped":
        # Skip goes to handle_error -> notify_user
        return "handle_error"
    # abort or exhausted -> handle_error -> notify_user
    return "handle_error"


def _after_handle_error(state: EpisodeAgentState) -> str:
    return "notify_user"


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
    builder.add_node(
        "search_resources", node_overrides.get("search_resources", SearchResourcesNode())
    )
    builder.add_node(
        "send_download",
        node_overrides.get("send_download", SendDownloadNode(session_factory=session_factory)),
    )
    builder.add_node("poll_download", node_overrides.get("poll_download", PollDownloadNode()))
    builder.add_node(
        "process_metadata", node_overrides.get("process_metadata", ProcessMetadataNode())
    )
    builder.add_node("organize_files", node_overrides.get("organize_files", OrganizeFilesNode()))
    builder.add_node("refresh_emby", node_overrides.get("refresh_emby", RefreshEmbyNode()))
    builder.add_node("human_review", node_overrides.get("human_review", HumanReviewNode()))
    builder.add_node("reflect_match", node_overrides.get("reflect_match", ReflectMatchNode()))
    builder.add_node("schedule_resume", node_overrides.get("schedule_resume", ScheduleResumeNode()))
    builder.add_node("handle_error", node_overrides.get("handle_error", HandleErrorNode()))
    builder.add_node("notify_user", node_overrides.get("notify_user", NotifyUserNode()))
    builder.add_node("error_handler", node_overrides.get("error_handler", ErrorHandlerNode()))

    builder.add_conditional_edges(START, _status_router)

    builder.add_conditional_edges("fetch_rss", _after_fetch_rss)
    builder.add_conditional_edges("match_torrent", _after_match_torrent)
    builder.add_conditional_edges("reflect_match", _after_reflect_match)
    builder.add_conditional_edges("search_resources", _after_search_resources)
    builder.add_conditional_edges("send_download", _after_send_download)
    builder.add_conditional_edges("poll_download", _after_poll_download)
    builder.add_conditional_edges("process_metadata", _after_process_metadata)
    builder.add_conditional_edges("organize_files", _after_organize_files)
    builder.add_conditional_edges("refresh_emby", _after_refresh_emby)
    builder.add_conditional_edges("handle_error", _after_handle_error)
    builder.add_conditional_edges("error_handler", _after_error_handler)
    builder.add_conditional_edges("human_review", _after_human_review)
    builder.add_edge("schedule_resume", END)
    builder.add_edge("notify_user", END)

    return builder.compile()

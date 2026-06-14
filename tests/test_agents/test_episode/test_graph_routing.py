"""Tests for all Episode Graph routing functions."""

from anime_agent.agents.episode.graph import (
    _after_error_handler,
    _after_fetch_rss,
    _after_handle_error,
    _after_human_review,
    _after_match_torrent,
    _after_organize_files,
    _after_poll_download,
    _after_process_metadata,
    _after_refresh_emby,
    _after_search_resources,
    _after_send_download,
    _status_router,
)
from anime_agent.agents.episode.state import EpisodeAgentState


def _state(status: str, **extra) -> EpisodeAgentState:
    base: EpisodeAgentState = {
        "goal_id": "sub_1_ep_1",
        "subscription_id": 1,
        "episode_number": 1,
        "rss_source_id": 1,
        "title_romaji": "Test",
        "title_native": "テスト",
        "title_chinese": "测试",
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
        "status": status,
        "errors": [],
        "requires_human": False,
        "human_input": None,
        "low_confidence_count": 0,
        "resume_after": None,
        "resource_searched": False,
    }
    base.update(extra)
    return base


# ── _status_router ──────────────────────────────────────────────────────


class TestStatusRouter:
    def test_pending_routes_to_fetch_rss(self):
        assert _status_router(_state("pending")) == "fetch_rss"

    def test_fetching_routes_to_fetch_rss(self):
        assert _status_router(_state("fetching")) == "fetch_rss"

    def test_matched_routes_to_send_download(self):
        assert _status_router(_state("matched")) == "send_download"

    def test_downloading_routes_to_poll_download(self):
        assert _status_router(_state("downloading")) == "poll_download"

    def test_downloaded_routes_to_process_metadata(self):
        assert _status_router(_state("downloaded")) == "process_metadata"

    def test_metadata_processed_routes_to_organize_files(self):
        assert _status_router(_state("metadata_processed")) == "organize_files"

    def test_organized_routes_to_refresh_emby(self):
        assert _status_router(_state("organized")) == "refresh_emby"

    def test_organized_with_warnings_routes_to_refresh_emby(self):
        assert _status_router(_state("organized_with_warnings")) == "refresh_emby"

    def test_human_review_routes_to_human_review(self):
        assert _status_router(_state("human_review")) == "human_review"

    def test_failed_routes_to_error_handler(self):
        assert _status_router(_state("failed")) == "error_handler"

    def test_unknown_status_defaults_to_fetch_rss(self):
        assert _status_router(_state("unknown_status")) == "fetch_rss"

    def test_missing_status_defaults_to_fetch_rss(self):
        assert _status_router({}) == "fetch_rss"


# ── _after_fetch_rss ────────────────────────────────────────────────────


class TestAfterFetchRSS:
    def test_failed_goes_to_error_handler(self):
        assert _after_fetch_rss(_state("failed")) == "error_handler"

    def test_fetching_goes_to_match_torrent(self):
        assert _after_fetch_rss(_state("fetching")) == "match_torrent"

    def test_waiting_goes_to_match_torrent(self):
        assert _after_fetch_rss(_state("waiting_for_rss")) == "match_torrent"


# ── _after_match_torrent ────────────────────────────────────────────────


class TestAfterMatchTorrent:
    def test_matched_goes_to_send_download(self):
        assert _after_match_torrent(_state("matched")) == "send_download"

    def test_search_resources_goes_to_search_resources(self):
        assert _after_match_torrent(_state("search_resources")) == "search_resources"

    def test_waiting_for_rss_goes_to_schedule_resume(self):
        assert _after_match_torrent(_state("waiting_for_rss")) == "schedule_resume"

    def test_low_confidence_goes_to_reflect_match(self):
        assert _after_match_torrent(_state("low_confidence")) == "reflect_match"

    def test_no_match_with_candidates_goes_to_reflect_match(self):
        s = _state("no_match", torrent_candidates=[{"info_hash": "abc"}])
        assert _after_match_torrent(s) == "reflect_match"

    def test_no_match_without_candidates_goes_to_schedule_resume(self):
        assert _after_match_torrent(_state("no_match")) == "schedule_resume"

    def test_unknown_goes_to_error_handler(self):
        assert _after_match_torrent(_state("something_else")) == "error_handler"


# ── _after_reflect_match ────────────────────────────────────────────────


class TestAfterReflectMatch:
    def test_matched_goes_to_send_download(self):
        assert _after_match_torrent(_state("matched")) == "send_download"

    def test_search_resources_goes_to_search_resources(self):
        from anime_agent.agents.episode.graph import _after_reflect_match
        assert _after_reflect_match(_state("search_resources")) == "search_resources"

    def test_schedule_resume_goes_to_schedule_resume(self):
        from anime_agent.agents.episode.graph import _after_reflect_match
        assert _after_reflect_match(_state("schedule_resume")) == "schedule_resume"

    def test_human_review_goes_to_human_review(self):
        from anime_agent.agents.episode.graph import _after_reflect_match
        assert _after_reflect_match(_state("human_review")) == "human_review"

    def test_unknown_goes_to_error_handler(self):
        from anime_agent.agents.episode.graph import _after_reflect_match
        assert _after_reflect_match(_state("unknown")) == "error_handler"


# ── _after_search_resources ─────────────────────────────────────────────


class TestAfterSearchResources:
    def test_searched_goes_to_match_torrent(self):
        assert _after_search_resources(_state("searched")) == "match_torrent"

    def test_failed_goes_to_schedule_resume(self):
        assert _after_search_resources(_state("failed")) == "schedule_resume"

    def test_unknown_goes_to_error_handler(self):
        assert _after_search_resources(_state("unknown")) == "error_handler"


# ── _after_send_download ────────────────────────────────────────────────


class TestAfterSendDownload:
    def test_downloading_goes_to_poll_download(self):
        assert _after_send_download(_state("downloading")) == "poll_download"

    def test_failed_goes_to_error_handler(self):
        assert _after_send_download(_state("failed")) == "error_handler"


# ── _after_poll_download ────────────────────────────────────────────────


class TestAfterPollDownload:
    def test_downloading_goes_to_schedule_resume(self):
        assert _after_poll_download(_state("downloading")) == "schedule_resume"

    def test_downloaded_goes_to_process_metadata(self):
        assert _after_poll_download(_state("downloaded")) == "process_metadata"

    def test_retry_match_goes_to_match_torrent(self):
        assert _after_poll_download(_state("retry_match")) == "match_torrent"

    def test_failed_goes_to_error_handler(self):
        assert _after_poll_download(_state("failed")) == "error_handler"


# ── _after_process_metadata ─────────────────────────────────────────────


class TestAfterProcessMetadata:
    def test_metadata_processed_goes_to_organize_files(self):
        assert _after_process_metadata(_state("metadata_processed")) == "organize_files"

    def test_failed_goes_to_error_handler(self):
        assert _after_process_metadata(_state("failed")) == "error_handler"


# ── _after_organize_files ───────────────────────────────────────────────


class TestAfterOrganizeFiles:
    def test_organized_goes_to_refresh_emby(self):
        assert _after_organize_files(_state("organized")) == "refresh_emby"

    def test_organized_with_warnings_goes_to_refresh_emby(self):
        assert _after_organize_files(_state("organized_with_warnings")) == "refresh_emby"

    def test_failed_goes_to_error_handler(self):
        assert _after_organize_files(_state("failed")) == "error_handler"


# ── _after_refresh_emby ─────────────────────────────────────────────────


class TestAfterRefreshEmby:
    def test_completed_goes_to_notify_user(self):
        assert _after_refresh_emby(_state("completed")) == "notify_user"

    def test_failed_goes_to_error_handler(self):
        assert _after_refresh_emby(_state("failed")) == "error_handler"


# ── _after_error_handler ────────────────────────────────────────────────


class TestAfterErrorHandler:
    def test_retry_fetch_rss_goes_to_fetch_rss(self):
        assert _after_error_handler(_state("retry_fetch_rss")) == "fetch_rss"

    def test_retry_send_download_goes_to_send_download(self):
        assert _after_error_handler(_state("retry_send_download")) == "send_download"

    def test_retry_organize_files_goes_to_organize_files(self):
        assert _after_error_handler(_state("retry_organize_files")) == "organize_files"

    def test_retry_unknown_goes_to_handle_error(self):
        assert _after_error_handler(_state("retry_nonexistent")) == "handle_error"

    def test_skipped_goes_to_handle_error(self):
        assert _after_error_handler(_state("skipped")) == "handle_error"

    def test_failed_goes_to_handle_error(self):
        assert _after_error_handler(_state("failed")) == "handle_error"

    def test_aborted_goes_to_handle_error(self):
        assert _after_error_handler(_state("aborted")) == "handle_error"


# ── _after_handle_error ─────────────────────────────────────────────────


class TestAfterHandleError:
    def test_always_goes_to_notify_user(self):
        assert _after_handle_error(_state("failed")) == "notify_user"
        assert _after_handle_error(_state("anything")) == "notify_user"


# ── _after_human_review ─────────────────────────────────────────────────


class TestAfterHumanReview:
    def test_matched_goes_to_send_download(self):
        assert _after_human_review(_state("matched")) == "send_download"

    def test_human_review_goes_to_end(self):
        from langgraph.graph import END
        assert _after_human_review(_state("human_review")) == END

    def test_other_goes_to_end(self):
        from langgraph.graph import END
        assert _after_human_review(_state("failed")) == END

"""Extended tests for conversational reply formatter — all query types and edge cases."""

from anime_agent.agents.conversational.reply import format_reply

# ── list_active ─────────────────────────────────────────────────────────


class TestListActive:
    def test_empty_list(self):
        reply = format_reply("list_active", [])
        assert "没有在追" in reply

    def test_multiple_subscriptions(self):
        data = [
            {"title": "Frieren", "total_episodes": 28, "completed": 10, "failed": 0},
            {"title": "Dandadan", "total_episodes": 12, "completed": 12, "failed": 0},
        ]
        reply = format_reply("list_active", data)
        assert "Frieren" in reply
        assert "Dandadan" in reply
        assert "10/28" in reply
        assert "12/12" in reply

    def test_no_failed_episodes(self):
        data = [{"title": "Test", "total_episodes": 12, "completed": 12, "failed": 0}]
        reply = format_reply("list_active", data)
        assert "失败" not in reply

    def test_unknown_total_episodes(self):
        data = [{"title": "Test", "total_episodes": None, "completed": 3, "failed": 0}]
        reply = format_reply("list_active", data)
        assert "3/?" in reply


# ── subscription_detail ─────────────────────────────────────────────────


class TestSubscriptionDetail:
    def test_with_all_fields(self):
        data = {"title": "Frieren", "total_episodes": 28, "completed": 20, "failed": 2, "pending": 6}
        reply = format_reply("subscription_detail", data)
        assert "共 28 集" in reply
        assert "已完成 20 集" in reply
        assert "待处理 6 集" in reply
        assert "失败 2 集" in reply

    def test_with_unknown_total(self):
        data = {"title": "Test", "total_episodes": None, "completed": 0, "failed": 0, "pending": 0}
        reply = format_reply("subscription_detail", data)
        assert "共 ? 集" in reply


# ── pending_torrents ────────────────────────────────────────────────────


class TestPendingTorrents:
    def test_empty_list(self):
        reply = format_reply("pending_torrents", [])
        assert "没有等待" in reply

    def test_multiple_pending(self):
        data = [
            {"title": "Frieren", "episode_number": 5, "status": "waiting_for_rss"},
            {"title": "Dandadan", "episode_number": 3, "status": "human_review"},
        ]
        reply = format_reply("pending_torrents", data)
        assert "Frieren" in reply
        assert "Dandadan" in reply


# ── anime_info ──────────────────────────────────────────────────────────


class TestAnimeInfo:
    def test_with_all_fields(self):
        data = {"title": "Frieren", "total_episodes": 28, "season": "FALL", "season_year": 2023}
        reply = format_reply("anime_info", data)
        assert "Frieren" in reply
        assert "2023 FALL" in reply
        assert "共 28 集" in reply

    def test_with_missing_season(self):
        data = {"title": "Frieren", "total_episodes": 28, "season": None, "season_year": None}
        reply = format_reply("anime_info", data)
        assert "Frieren" in reply
        assert "共 28 集" in reply

    def test_with_unknown_total(self):
        data = {"title": "Test", "total_episodes": None, "season": "SPRING", "season_year": 2024}
        reply = format_reply("anime_info", data)
        assert "未知" in reply


# ── failed_tasks ────────────────────────────────────────────────────────


class TestFailedTasks:
    def test_empty_list(self):
        reply = format_reply("failed_tasks", [])
        assert "没有失败" in reply

    def test_with_error_log(self):
        data = [{"title": "Frieren", "episode_number": 5, "error_log": "Connection timeout to qBittorrent server"}]
        reply = format_reply("failed_tasks", data)
        assert "Frieren" in reply
        assert "第 5 集" in reply
        assert "Connection timeout" in reply

    def test_without_error_log(self):
        data = [{"title": "Frieren", "episode_number": 5}]
        reply = format_reply("failed_tasks", data)
        assert "Frieren" in reply


# ── Unknown query type ──────────────────────────────────────────────────


class TestUnknownQuery:
    def test_returns_fallback_message(self):
        reply = format_reply("unknown_type", {"some": "data"})
        assert "没太听懂" in reply


# ── None data ───────────────────────────────────────────────────────────


class TestNoneData:
    def test_returns_not_subscribed_message(self):
        reply = format_reply("subscription_detail", None)
        assert "还没有订阅" in reply

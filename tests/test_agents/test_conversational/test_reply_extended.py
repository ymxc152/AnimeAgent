"""Extended tests for conversational reply formatter — all action types."""

from unittest.mock import AsyncMock, MagicMock

from anime_agent.agents.conversational.reply import format_reply, llm_polish

# ── Help ────────────────────────────────────────────────────────────────


class TestHelp:
    def test_returns_help_text(self):
        reply = format_reply("help", None)
        assert "追番" in reply
        assert "订阅" in reply


# ── Subscribe ───────────────────────────────────────────────────────────


class TestSubscribe:
    def test_shows_candidates(self):
        data = [
            {
                "title_chinese": "葬送的芙莉莲",
                "title_romaji": "Frieren",
                "season_year": 2023,
                "total_episodes": 28,
            },
            {
                "title_chinese": "进击的巨人",
                "title_romaji": "AoT",
                "season_year": 2013,
                "total_episodes": 25,
            },
        ]
        reply = format_reply("subscribe", data, title="芙莉莲")
        assert "葬送的芙莉莲" in reply
        assert "进击的巨人" in reply
        assert "第 N 个" in reply

    def test_no_candidates(self):
        reply = format_reply("subscribe", [], title="不存在的番")
        assert "没有找到" in reply

    def test_no_title(self):
        reply = format_reply("subscribe", None, title=None)
        assert "想订阅什么" in reply

    def test_subscribe_confirmed(self):
        reply = format_reply("subscribe_confirmed", None, title="葬送的芙莉莲")
        assert "已成功订阅" in reply
        assert "葬送的芙莉莲" in reply


# ── Select candidate ────────────────────────────────────────────────────


class TestSelectCandidate:
    def test_no_candidates_in_context(self):
        reply = format_reply("select_candidate", None)
        assert "没有可选择" in reply


# ── Retry episode ───────────────────────────────────────────────────────


class TestRetryEpisode:
    def test_retry_success(self):
        data = {"success": True, "episode_number": 5}
        reply = format_reply("retry_episode", data, title="葬送的芙莉莲")
        assert "已重置" in reply
        assert "第 5 集" in reply

    def test_retry_not_found(self):
        data = {"success": False}
        reply = format_reply("retry_episode", data, title="葬送的芙莉莲")
        assert "没有找到" in reply


# ── Query status ────────────────────────────────────────────────────────


class TestQueryStatus:
    def test_list_active(self):
        data = [{"title": "Frieren", "total_episodes": 28, "completed": 10, "failed": 0}]
        reply = format_reply("query_status", data, query_type="list_active")
        assert "Frieren" in reply
        assert "10/28" in reply

    def test_list_active_empty(self):
        reply = format_reply("query_status", [], query_type="list_active")
        assert "没有在追" in reply

    def test_subscription_detail(self):
        data = {
            "title": "Frieren",
            "total_episodes": 28,
            "completed": 20,
            "failed": 2,
            "pending": 6,
        }
        reply = format_reply("query_status", data, query_type="subscription_detail")
        assert "共 28 集" in reply

    def test_pending_torrents_empty(self):
        reply = format_reply("query_status", [], query_type="pending_torrents")
        assert "没有等待" in reply

    def test_failed_tasks_empty(self):
        reply = format_reply("query_status", [], query_type="failed_tasks")
        assert "没有失败" in reply

    def test_anime_info(self):
        data = {"title": "Frieren", "total_episodes": 28, "season": "FALL", "season_year": 2023}
        reply = format_reply("query_status", data, query_type="anime_info")
        assert "Frieren" in reply

    def test_none_data(self):
        reply = format_reply("query_status", None, query_type="subscription_detail")
        assert "还没有订阅" in reply


# ── Unknown action ──────────────────────────────────────────────────────


class TestUnknown:
    def test_returns_fallback(self):
        reply = format_reply("unknown_action", {"some": "data"})
        assert "没太听懂" in reply


# ── llm_polish ──────────────────────────────────────────────────────────


class TestLLMPolish:
    async def test_returns_polished_text(self):
        mock_llm = AsyncMock()
        mock_llm.invoke.return_value = MagicMock(
            success=True,
            data={"text": "你正在追的番有芙莉莲，已经看了10集了。"},
        )

        result = await llm_polish(mock_llm, "我在追什么番", "模板回复", [{"title": "Frieren"}])
        assert result == "你正在追的番有芙莉莲，已经看了10集了。"

    async def test_falls_back_on_llm_failure(self):
        mock_llm = AsyncMock()
        mock_llm.invoke.return_value = MagicMock(success=False, error="API error")

        result = await llm_polish(mock_llm, "test", "模板回复", None)
        assert result == "模板回复"

    async def test_falls_back_on_exception(self):
        mock_llm = AsyncMock()
        mock_llm.invoke.side_effect = Exception("Network error")

        result = await llm_polish(mock_llm, "test", "模板回复", None)
        assert result == "模板回复"

    async def test_falls_back_when_polished_same_as_template(self):
        mock_llm = AsyncMock()
        mock_llm.invoke.return_value = MagicMock(
            success=True,
            data={"text": "模板回复"},
        )

        result = await llm_polish(mock_llm, "test", "模板回复", None)
        assert result == "模板回复"

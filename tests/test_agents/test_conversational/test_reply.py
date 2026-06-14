"""Tests for conversational reply formatter."""

from anime_agent.agents.conversational.reply import format_reply


def test_format_list_active():
    """Should format active subscription list."""
    data = [
        {"title": "Frieren", "total_episodes": 28, "completed": 10, "failed": 1},
    ]
    reply = format_reply("list_active", data)
    assert "Frieren" in reply
    assert "10/28" in reply
    assert "失败 1 集" in reply


def test_format_subscription_detail():
    """Should format subscription progress."""
    data = {"title": "Frieren", "total_episodes": 28, "completed": 28, "failed": 0, "pending": 0}
    reply = format_reply("subscription_detail", data)
    assert "共 28 集" in reply
    assert "已完成 28 集" in reply


def test_format_pending_torrents():
    """Should format pending torrents."""
    data = [{"title": "Test", "episode_number": 5, "status": "waiting_for_rss"}]
    reply = format_reply("pending_torrents", data)
    assert "Test" in reply
    assert "第 5 集" in reply


def test_format_anime_info():
    """Should format anime metadata."""
    data = {"title": "Frieren", "total_episodes": 28, "season": "FALL", "season_year": 2023}
    reply = format_reply("anime_info", data)
    assert "2023 FALL" in reply
    assert "共 28 集" in reply


def test_format_unknown_title():
    """Should suggest help for unknown titles."""
    reply = format_reply("subscription_detail", None, "missing")
    assert "还没有订阅" in reply

"""Tests for conversational intent parser."""

import pytest

from anime_agent.agents.conversational.intent import parse_intent


@pytest.mark.parametrize(
    ("text", "expected_action", "expected_query_type", "expected_title"),
    [
        ("我在下载哪些番？", "query_status", "list_active", None),
        ("我在追哪些番", "query_status", "list_active", None),
        ("《葬送的芙莉莲》下完了吗？", "query_status", "subscription_detail", "葬送的芙莉莲"),
        ("芙莉莲进度怎么样", "query_status", "subscription_detail", "芙莉莲"),
        ("《鬼灭之刃》有多少集？", "query_status", "anime_info", "鬼灭之刃"),
        ("有哪些番还在等种子？", "query_status", "pending_torrents", None),
        ("最近失败的任务有哪些？", "query_status", "failed_tasks", None),
        ("hello world", "unknown", None, None),
    ],
)
def test_parse_intent(text, expected_action, expected_query_type, expected_title):
    """Intent parser should map common Chinese questions to structured intents."""
    intent = parse_intent(text)
    assert intent.action == expected_action
    assert intent.query_type == expected_query_type
    assert intent.title == expected_title

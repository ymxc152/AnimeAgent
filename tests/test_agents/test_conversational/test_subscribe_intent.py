"""Tests for new intent types: subscribe, retry, help, select."""

from anime_agent.agents.conversational.intent import parse_intent


def test_subscribe_intent_chinese():
    intent = parse_intent("订阅 葬送的芙莉莲")
    assert intent.action == "subscribe"
    assert intent.title == "葬送的芙莉莲"


def test_subscribe_intent_with_quotes():
    intent = parse_intent("帮我追《咒术回战》")
    assert intent.action == "subscribe"
    assert intent.title == "咒术回战"


def test_subscribe_intent_english():
    intent = parse_intent("subscribe Frieren")
    assert intent.action == "subscribe"
    assert intent.title == "Frieren"


def test_subscribe_intent_no_title():
    intent = parse_intent("订阅")
    assert intent.action == "subscribe"
    assert intent.title is None


def test_retry_intent_chinese():
    intent = parse_intent("重试 葬送的芙莉莲 第5集")
    assert intent.action == "retry_episode"
    assert intent.title == "葬送的芙莉莲"
    assert intent.episode_number == 5


def test_retry_intent_english():
    intent = parse_intent("retry Frieren ep 3")
    assert intent.action == "retry_episode"
    assert intent.episode_number == 3


def test_retry_intent_no_episode():
    intent = parse_intent("重试 葬送的芙莉莲")
    assert intent.action == "retry_episode"
    assert intent.title == "葬送的芙莉莲"
    assert intent.episode_number is None


def test_help_intent_chinese():
    intent = parse_intent("帮助")
    assert intent.action == "help"


def test_help_intent_english():
    intent = parse_intent("help")
    assert intent.action == "help"


def test_help_intent_can_you_do():
    intent = parse_intent("你能做什么")
    assert intent.action == "help"


def test_select_candidate_first():
    intent = parse_intent("第一个")
    assert intent.action == "select_candidate"
    assert intent.selection_index == 1


def test_select_candidate_number():
    intent = parse_intent("第 3 个")
    assert intent.action == "select_candidate"
    assert intent.selection_index == 3


def test_select_candidate_bare_number():
    intent = parse_intent("2")
    assert intent.action == "select_candidate"
    assert intent.selection_index == 2


def test_select_candidate_with_prefix():
    intent = parse_intent("选 3")
    assert intent.action == "select_candidate"
    assert intent.selection_index == 3


def test_subscribe_before_query():
    """Subscribe keywords should take precedence over query keywords."""
    intent = parse_intent("订阅葬送的芙莉莲进度")
    assert intent.action == "subscribe"

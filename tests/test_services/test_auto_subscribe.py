"""Tests for auto-subscribe rule matching and LLM filter."""

from unittest.mock import AsyncMock

import pytest

from anime_agent.services.auto_subscribe_llm_filter import (
    AutoSubscribeLLMFilter,
    AutoSubscribeRuleMatcher,
)


class FakeRule:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


@pytest.fixture
def sample_anime():
    return {
        "title_chinese": "葬送的芙莉莲",
        "title_romaji": "Sousou no Frieren",
        "title_native": "葬送のフリーレン",
        "format": "TV",
        "genres": ["Adventure", "Fantasy"],
        "tags": ["Iyashikei"],
        "total_episodes": 28,
        "score": 85,
    }


class TestAutoSubscribeRuleMatcher:
    def test_matches_by_genre(self, sample_anime):
        rule = FakeRule(
            enabled=True,
            include_genres="Fantasy",
            exclude_genres=None,
            include_formats=None,
            exclude_formats=None,
            include_keywords=None,
            exclude_keywords=None,
            min_score=None,
        )
        matcher = AutoSubscribeRuleMatcher([rule])
        assert matcher.matches(sample_anime) == [rule]

    def test_excludes_by_format(self, sample_anime):
        rule = FakeRule(
            enabled=True,
            include_genres=None,
            exclude_genres=None,
            include_formats=None,
            exclude_formats="MOVIE",
            include_keywords=None,
            exclude_keywords=None,
            min_score=None,
        )
        matcher = AutoSubscribeRuleMatcher([rule])
        assert matcher.matches(sample_anime) == [rule]

    def test_matches_by_keyword(self, sample_anime):
        rule = FakeRule(
            enabled=True,
            include_genres=None,
            exclude_genres=None,
            include_formats=None,
            exclude_formats=None,
            include_keywords="芙莉莲",
            exclude_keywords=None,
            min_score=None,
        )
        matcher = AutoSubscribeRuleMatcher([rule])
        assert matcher.matches(sample_anime) == [rule]

    def test_disabled_rule_is_ignored(self, sample_anime):
        rule = FakeRule(
            enabled=False,
            include_genres="Fantasy",
            exclude_genres=None,
            include_formats=None,
            exclude_formats=None,
            include_keywords=None,
            exclude_keywords=None,
            min_score=None,
        )
        matcher = AutoSubscribeRuleMatcher([rule])
        assert matcher.matches(sample_anime) == []

    def test_min_score_filters(self, sample_anime):
        rule = FakeRule(
            enabled=True,
            include_genres=None,
            exclude_genres=None,
            include_formats=None,
            exclude_formats=None,
            include_keywords=None,
            exclude_keywords=None,
            min_score=90,
        )
        matcher = AutoSubscribeRuleMatcher([rule])
        assert matcher.matches(sample_anime) == []


class TestAutoSubscribeLLMFilter:
    async def test_decide_subscribe(self, sample_anime):
        tool = AsyncMock()
        tool.invoke.return_value = AsyncMock(success=True, data="subscribe")
        filter_ = AutoSubscribeLLMFilter(llm_tool=tool)
        assert await filter_.decide(sample_anime) == "subscribe"

    async def test_decide_skip(self, sample_anime):
        tool = AsyncMock()
        tool.invoke.return_value = AsyncMock(success=True, data="skip")
        filter_ = AutoSubscribeLLMFilter(llm_tool=tool)
        assert await filter_.decide(sample_anime) == "skip"

    async def test_decide_human_review_on_failure(self, sample_anime):
        tool = AsyncMock()
        tool.invoke.side_effect = RuntimeError("llm down")
        filter_ = AutoSubscribeLLMFilter(llm_tool=tool)
        assert await filter_.decide(sample_anime) == "human_review"

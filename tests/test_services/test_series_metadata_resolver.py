"""Tests for SeriesMetadataResolver."""

from unittest.mock import AsyncMock

import pytest

from anime_agent.services.series_metadata_resolver import SeriesMetadataResolver
from anime_agent.tools.base import ToolOutput


@pytest.mark.asyncio
async def test_rule_based_strips_chinese_season():
    resolver = SeriesMetadataResolver(llm_tool=AsyncMock())
    meta = await resolver.resolve({"title_chinese": "测试动画 第二季"})
    assert meta.series_title == "测试动画"
    assert meta.season_number == 2


@pytest.mark.asyncio
async def test_rule_based_strips_english_season():
    resolver = SeriesMetadataResolver(llm_tool=AsyncMock())
    meta = await resolver.resolve({"title_romaji": "Test Anime 2nd Season"})
    assert meta.series_title == "Test Anime"
    assert meta.season_number == 2


@pytest.mark.asyncio
async def test_rule_based_defaults_to_season_one():
    resolver = SeriesMetadataResolver(llm_tool=AsyncMock())
    meta = await resolver.resolve({"title_chinese": "测试动画"})
    assert meta.series_title == "测试动画"
    assert meta.season_number == 1


@pytest.mark.asyncio
async def test_llm_fallback_when_rules_uncertain():
    llm_tool = AsyncMock()
    llm_tool.invoke.return_value = ToolOutput(
        success=True,
        data={"json": {"series_title": "Base Name", "season_number": 3}},
    )
    resolver = SeriesMetadataResolver(llm_tool=llm_tool)

    # A bare trailing number is ambiguous, so the resolver should ask the LLM.
    meta = await resolver.resolve({"title_romaji": "Some Anime 3"})

    assert meta.series_title == "Base Name"
    assert meta.season_number == 3
    llm_tool.invoke.assert_awaited_once()


@pytest.mark.asyncio
async def test_llm_failure_falls_back_to_raw_title():
    llm_tool = AsyncMock()
    llm_tool.invoke.return_value = ToolOutput(success=False, error="timeout")
    resolver = SeriesMetadataResolver(llm_tool=llm_tool)
    meta = await resolver.resolve({"title_romaji": "Weird Sequel Naming"})
    assert meta.series_title == "Weird Sequel Naming"
    assert meta.season_number == 1

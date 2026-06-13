"""Tests for BangumiTool."""

import respx
from httpx import Response

from anime_agent.tools.bangumi_tool import BangumiTool, BangumiToolInput


@respx.mock
async def test_bangumi_tool_searches_anime():
    """BangumiTool should search anime by keyword and return normalized results."""
    api_response = {
        "results": 1,
        "list": [
            {
                "id": 123,
                "name": "葬送的芙莉莲",
                "name_cn": "葬送的芙莉莲",
                "type": 2,
                "air_date": "2023-09-29",
                "images": {"large": "https://example.com/large.jpg"},
            }
        ],
    }
    route = respx.get("https://api.bgm.tv/search/subject/%E8%91%AC%E9%80%81%E7%9A%84%E8%8A%99%E8%8E%89%E8%8E%B2").mock(
        return_value=Response(200, json=api_response)
    )

    tool = BangumiTool()
    result = await tool.invoke(BangumiToolInput(action="search", query="葬送的芙莉莲"))

    assert result.success is True
    assert len(result.data["subjects"]) == 1
    subject = result.data["subjects"][0]
    assert subject["bangumi_id"] == 123
    assert subject["title_chinese"] == "葬送的芙莉莲"
    assert subject["title_native"] == "葬送的芙莉莲"
    assert subject["air_date"] == "2023-09-29"
    assert route.called


@respx.mock
async def test_bangumi_tool_gets_subject_details():
    """BangumiTool should fetch detailed subject information."""
    api_response = {
        "id": 123,
        "name": "Sousou no Frieren",
        "name_cn": "葬送的芙莉莲",
        "type": 2,
        "eps": 28,
        "air_date": "2023-09-29",
        "summary": "A story about an elf mage.",
        "tags": [{"name": "奇幻"}, {"name": "冒险"}],
        "images": {"large": "https://example.com/large.jpg"},
    }
    route = respx.get("https://api.bgm.tv/v0/subjects/123").mock(return_value=Response(200, json=api_response))

    tool = BangumiTool()
    result = await tool.invoke(BangumiToolInput(action="details", subject_id=123))

    assert result.success is True
    details = result.data["subject"]
    assert details["bangumi_id"] == 123
    assert details["title_romaji"] == "Sousou no Frieren"
    assert details["title_chinese"] == "葬送的芙莉莲"
    assert details["total_episodes"] == 28
    assert details["tags"] == ["奇幻", "冒险"]
    assert route.called


@respx.mock
async def test_bangumi_tool_seasonal_filters_calendar_by_year_and_season():
    """BangumiTool seasonal should filter calendar results by air_date."""
    api_response = [
        {
            "weekday": {"en": "Mon"},
            "items": [
                {
                    "id": 1,
                    "name": "Winter Show",
                    "name_cn": "冬季番",
                    "type": 2,
                    "air_date": "2024-01-15",
                },
                {
                    "id": 2,
                    "name": "Spring Show",
                    "name_cn": "春季番",
                    "type": 2,
                    "air_date": "2024-04-10",
                },
            ],
        }
    ]
    route = respx.get("https://api.bgm.tv/calendar").mock(return_value=Response(200, json=api_response))

    tool = BangumiTool()
    result = await tool.invoke(BangumiToolInput(action="seasonal", year=2024, season="WINTER"))

    assert result.success is True
    assert route.called
    subjects = result.data["subjects"]
    assert len(subjects) == 1
    assert subjects[0]["bangumi_id"] == 1
    assert subjects[0]["title_chinese"] == "冬季番"


@respx.mock
async def test_bangumi_tool_returns_error_on_http_failure():
    """BangumiTool should return failed ToolOutput on HTTP errors."""
    respx.get("https://api.bgm.tv/search/subject/test").mock(return_value=Response(500))

    tool = BangumiTool()
    result = await tool.invoke(BangumiToolInput(action="search", query="test"))

    assert result.success is False
    assert result.error

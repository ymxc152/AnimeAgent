"""Real-data smoke test for BangumiTool."""

import pytest

from anime_agent.tools.bangumi_tool import BangumiTool, BangumiToolInput


@pytest.mark.real_data
async def test_bangumi_details_returns_anime() -> None:
    """Bangumi should return details for a known subject."""
    tool = BangumiTool()
    result = await tool.invoke(BangumiToolInput(action="details", subject_id=160209))
    assert result.success, result.error
    subject = result.data.get("subject", {})
    assert subject.get("title_chinese") or subject.get("title_romaji")

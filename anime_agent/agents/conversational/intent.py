"""Rule-based intent parser for conversational status queries."""

from typing import Any


class ParsedIntent:
    """Parsed user intent for the conversational agent."""

    def __init__(
        self,
        action: str,
        query_type: str | None = None,
        title: str | None = None,
    ):
        self.action = action
        self.query_type = query_type
        self.title = title

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "query_type": self.query_type,
            "title": self.title,
        }


def parse_intent(text: str) -> ParsedIntent:
    """Parse a Chinese or mixed status query into a structured intent.

    This is intentionally rule-based so it works without an LLM call for
    common questions. The reply layer can still use an LLM to summarize the
    structured result if desired.
    """
    lowered = text.lower().strip()

    # Pending torrents / waiting (check before generic list phrases)
    if any(
        kw in lowered
        for kw in (
            "等种子",
            "还在等",
            "pending",
            "waiting",
            "没种子",
            "需要人工",
            "人工审核",
        )
    ):
        return ParsedIntent("query_status", query_type="pending_torrents")

    # Failed tasks
    if any(
        kw in lowered
        for kw in (
            "失败",
            "failed",
            "报错",
            "出错",
        )
    ) and "下完了" not in lowered:
        return ParsedIntent("query_status", query_type="failed_tasks")

    # Subscription detail / progress
    if any(
        kw in lowered
        for kw in (
            "下完了吗",
            "下载完了吗",
            "进度",
            "progress",
            "status",
        )
    ):
        title = _extract_title(lowered)
        return ParsedIntent("query_status", query_type="subscription_detail", title=title)

    # Anime info / episode count
    if any(
        kw in lowered
        for kw in (
            "多少集",
            "有几集",
            "total",
            "episodes",
            "信息",
            "info",
        )
    ):
        title = _extract_title(lowered)
        return ParsedIntent("query_status", query_type="anime_info", title=title)

    # List active / all subscriptions
    if any(
        kw in lowered
        for kw in (
            "我在下载哪些",
            "我在追哪些",
            "有哪些番",
            "追了哪些",
            "list",
            "active",
        )
    ):
        return ParsedIntent("query_status", query_type="list_active")

    return ParsedIntent("unknown")


def _extract_title(text: str) -> str | None:
    """Heuristic extraction of a quoted or bookended title."""
    # 《title》 or "title" or 'title'
    import re

    m = re.search(r'[《"\']([^《"\']+)[》"\']', text)
    if m:
        return m.group(1).strip()

    # Strip common query suffixes and return remainder as title
    suffixes = [
        "下完了吗",
        "下载完了吗",
        "进度怎么样",
        "进度如何",
        "多少集",
        "有几集",
        "的信息",
        "status",
        "progress",
    ]
    for suffix in suffixes:
        if text.endswith(suffix):
            return text[: -len(suffix)].strip() or None
    return None

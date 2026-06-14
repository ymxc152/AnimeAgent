"""Rule-based intent parser for conversational status queries."""

from __future__ import annotations

import re
from typing import Any


class ParsedIntent:
    """Parsed user intent for the conversational agent."""

    def __init__(
        self,
        action: str,
        query_type: str | None = None,
        title: str | None = None,
        episode_number: int | None = None,
        anilist_id: int | None = None,
        bangumi_id: int | None = None,
        selection_index: int | None = None,
    ):
        self.action = action
        self.query_type = query_type
        self.title = title
        self.episode_number = episode_number
        self.anilist_id = anilist_id
        self.bangumi_id = bangumi_id
        self.selection_index = selection_index

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "query_type": self.query_type,
            "title": self.title,
            "episode_number": self.episode_number,
            "anilist_id": self.anilist_id,
            "bangumi_id": self.bangumi_id,
            "selection_index": self.selection_index,
        }


def parse_intent(text: str) -> ParsedIntent:
    """Parse a Chinese or mixed status query into a structured intent.

    This is intentionally rule-based so it works without an LLM call for
    common questions. The reply layer can still use an LLM to summarize the
    structured result if desired.
    """
    lowered = text.lower().strip()

    # --- Selection (e.g. "第一个", "第 2 个") — check early for confirm flow ---
    selection = _extract_selection(lowered)
    if selection is not None:
        return ParsedIntent("select_candidate", selection_index=selection)

    # --- Subscribe intent ---
    if any(
        kw in lowered
        for kw in (
            "订阅",
            "追番",
            "subscribe",
            "帮我追",
            "我想看",
            "想追",
            "帮我找",
        )
    ):
        title = _extract_title(lowered)
        return ParsedIntent("subscribe", title=title)

    # --- Retry intent ---
    if any(
        kw in lowered
        for kw in (
            "重试",
            "retry",
            "再试一次",
            "重新下载",
            "再下载",
        )
    ):
        title = _extract_title(lowered)
        ep = _extract_episode_number(lowered)
        return ParsedIntent("retry_episode", title=title, episode_number=ep)

    # --- Help intent ---
    if any(
        kw in lowered
        for kw in (
            "帮助",
            "help",
            "你能做什么",
            "你会什么",
            "有什么功能",
            "怎么用",
        )
    ):
        return ParsedIntent("help")

    # --- Pending torrents / waiting ---
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

    # --- Failed tasks ---
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

    # --- Subscription detail / progress ---
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

    # --- Anime info / episode count ---
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

    # --- List active / all subscriptions ---
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


def _extract_selection(text: str) -> int | None:
    """Extract a selection index like '第一个', '第2个', '1', '选 3'."""
    m = re.search(r"第\s*(\d+)\s*个", text)
    if m:
        return int(m.group(1))
    # Bare number at start/end when short text (e.g. "1", "选 2")
    m = re.match(r"^(?:选\s*)?(\d+)$", text.strip())
    if m:
        return int(m.group(1))
    return None


def _extract_episode_number(text: str) -> int | None:
    """Extract an episode number like '第5集', 'ep 3', 'E12'."""
    m = re.search(r"第\s*(\d+)\s*集", text)
    if m:
        return int(m.group(1))
    m = re.search(r"\bep(?:isode)?\s*(\d+)", text, re.IGNORECASE)
    if m:
        return int(m.group(1))
    return None


def _extract_title(text: str) -> str | None:
    """Heuristic extraction of a quoted or bookended title."""
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
        # Subscribe suffixes
        "订阅",
        "追番",
        "帮我追",
        "我想看",
        "想追",
        "帮我找",
        # Retry suffixes
        "重试",
        "retry",
        "再试一次",
        "重新下载",
        "再下载",
    ]
    for suffix in suffixes:
        if text.endswith(suffix):
            return text[: -len(suffix)].strip() or None
    return None

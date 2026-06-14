"""Template-based reply formatter for conversational status queries."""

from __future__ import annotations

import json
from typing import Any, cast

from anime_agent.tools.llm_tool import LLMTool, LLMToolInput

# Query types that were previously passed as the first positional argument.
_QUERY_TYPES = {
    "list_active",
    "subscription_detail",
    "pending_torrents",
    "anime_info",
    "failed_tasks",
}


def format_reply(
    action: str,
    data: Any,
    title: str | None = None,
    query_type: str | None = None,
) -> str:
    """Format a structured query result as a natural-language reply."""

    # Backward compatibility: older callers passed query_type as the first arg.
    if action in _QUERY_TYPES:
        return _format_query_reply(action, data, title)

    # --- Help ---
    if action == "help":
        return (
            '我可以帮你：\n'
            '- 查看追番列表和下载进度\n'
            '- 查看某部番的详细信息\n'
            '- 查看等待种子或需要审核的剧集\n'
            '- 查看失败的下载任务\n'
            '- 订阅新番（说"订阅 作品名"）\n'
            '- 重试失败的下载（说"重试 作品名"）\n'
            '试试直接问我吧！'
        )

    # --- Subscribe: show search candidates ---
    if action == "subscribe" and isinstance(data, list):
        if not data:
            return f'没有找到与"{title}"相关的番剧，换个关键词试试？'
        lines = [f'找到以下与"{title}"相关的番剧：']
        for i, item in enumerate(data, 1):
            t = item.get("title_chinese") or item.get("title_romaji") or item.get("title_native") or "未知"
            year = item.get("season_year") or ""
            eps = item.get("total_episodes") or "?"
            lines.append(f"{i}. 《{t}》 ({year}) — {eps} 集")
        lines.append('\n回复"第 N 个"来选择订阅。')
        return "\n".join(lines)

    # --- Subscribe: no title provided ---
    if action == "subscribe" and not title:
        return '你想订阅什么番？告诉我作品名就好，比如"订阅 葬送的芙莉莲"。'

    # --- Subscribe: confirm success ---
    if action == "subscribe_confirmed":
        return f"已成功订阅《{title}》！我会自动帮你追踪和下载。"

    # --- Select candidate: no candidates in context ---
    if action == "select_candidate" and data is None:
        return "当前没有可选择的候选。请先搜索要订阅的番剧。"

    # --- Retry episode ---
    if action == "retry_episode":
        if data and data.get("success"):
            ep = data.get("episode_number", "?")
            return f"已重置《{title}》第 {ep} 集，将重新尝试下载。"
        return "没有找到需要重试的剧集。请确认番名和集数。"

    # --- Query status actions (original logic) ---
    if action == "query_status":
        return _format_query_reply(query_type or "unknown", data, title)

    # --- Fallback ---
    return '我没太听懂，你可以换种方式问我。试试说"帮助"看看我能做什么。'


def _format_query_reply(
    query_type: str, data: Any, title: str | None = None
) -> str:
    """Format reply for query_status sub-types."""
    if data is None:
        return "你还没有订阅这部番，需要我帮你找一下吗？"

    if query_type == "list_active":
        if not data:
            return "你当前没有在追的番剧。"
        lines = ["你当前在追的番剧："]
        for item in data:
            total = item.get("total_episodes") or "?"
            completed = item.get("completed", 0)
            failed = item.get("failed", 0)
            lines.append(
                f"- 《{item['title']}》：{completed}/{total} 集已完成"
                + (f"，失败 {failed} 集" if failed else "")
            )
        return "\n".join(lines)

    if query_type == "subscription_detail":
        total = data.get("total_episodes") or "?"
        completed = data.get("completed", 0)
        failed = data.get("failed", 0)
        pending = data.get("pending", 0)
        return (
            f"《{data['title']}》共 {total} 集，"
            f"已完成 {completed} 集，待处理 {pending} 集，失败 {failed} 集。"
        )

    if query_type == "pending_torrents":
        if not data:
            return "当前没有等待种子或人工审核的剧集。"
        lines = ["以下剧集还在等种子或审核："]
        for item in data:
            lines.append(
                f"- 《{item['title']}》第 {item['episode_number']} 集（{item['status']}）"
            )
        return "\n".join(lines)

    if query_type == "anime_info":
        total = data.get("total_episodes") or "未知"
        season = data.get("season") or ""
        year = data.get("season_year") or ""
        season_text = f"{year} {season}".strip()
        return (
            f"《{data['title']}》"
            + (f"，{season_text}" if season_text else "")
            + f"，共 {total} 集。"
        )

    if query_type == "failed_tasks":
        if not data:
            return "最近没有失败的下载任务。"
        lines = ["最近的失败任务："]
        for item in data:
            lines.append(
                f"- 《{item['title']}》第 {item['episode_number']} 集"
                + (f"：{item['error_log'][:60]}" if item.get("error_log") else "")
            )
        return "\n".join(lines)

    return "我没太听懂，你可以换种方式问我。"


# ---------------------------------------------------------------------------
# LLM polish layer
# ---------------------------------------------------------------------------

_POLISH_SYSTEM = (
    "你是 AnimeAgent 助手，一个帮助用户管理动漫追番和下载的 AI。\n"
    "你的回复应该简洁、友好、使用中文。\n"
    "基于给定的结构化查询结果，用自然流畅的语言重新组织回复。\n"
    "不要编造数据，只基于提供的数据回复。\n"
    "如果数据中包含列表，保持列表格式但让语言更自然。"
)


async def llm_polish(
    llm_tool: LLMTool,
    user_input: str,
    structured_reply: str,
    data: Any,
    history: list[dict[str, str]] | None = None,
) -> str | None:
    """Use LLM to make the template reply more natural, with conversation context.

    Falls back to the structured reply on any LLM error.
    """
    history_lines = ""
    if history:
        recent = history[-6:]  # last 3 turns
        parts = []
        for msg in recent:
            role = "用户" if msg.get("role") == "user" else "助手"
            parts.append(f"{role}: {msg.get('content', '')}")
        history_lines = "\n".join(parts)

    data_text = ""
    if data is not None:
        try:
            data_text = json.dumps(data, ensure_ascii=False, indent=2)
        except (TypeError, ValueError):
            data_text = str(data)

    user_prompt = (
        f"用户问题：{user_input}\n\n"
        f"结构化查询结果：\n{data_text}\n\n"
        f"模板回复：\n{structured_reply}\n"
    )
    if history_lines:
        user_prompt = f"最近对话：\n{history_lines}\n\n{user_prompt}"

    user_prompt += "\n请用自然流畅的中文回复用户（不要用 markdown 格式）："

    try:
        result = await llm_tool.invoke(
            LLMToolInput(
                prompt=user_prompt,
                system_msg=_POLISH_SYSTEM,
                temperature=0.7,
            )
        )
        if result.success and result.data:
            polished = cast(str, result.data.get("text", "")).strip()
            if polished and polished != structured_reply:
                return polished
    except Exception:  # noqa: BLE001
        pass

    return None

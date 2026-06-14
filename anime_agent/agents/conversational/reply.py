"""Template-based reply formatter for conversational status queries."""

from typing import Any


def format_reply(query_type: str, data: Any, title: str | None = None) -> str:
    """Format a structured query result as a natural-language reply."""
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

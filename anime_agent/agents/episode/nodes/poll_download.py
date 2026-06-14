"""poll_download node — LLM-driven agent for download monitoring."""

from datetime import UTC, datetime, timedelta
from typing import Any

from anime_agent.agents.episode.agent_prompts import (
    POLL_DOWNLOAD_ACTIONS,
    POLL_DOWNLOAD_SYSTEM,
)
from anime_agent.agents.episode.base_agent import BaseAgentNode
from anime_agent.config import settings
from anime_agent.services.torrent_health import TorrentHealth
from anime_agent.tools.base import BaseTool
from anime_agent.tools.bash_tool import BashToolInput
from anime_agent.tools.qb_tool import QBTool, QBToolInput
from anime_agent.utils.logger import logger


class PollDownloadNode(BaseAgentNode):
    """LLM-driven download monitoring agent.

    Instead of fixed thresholds (1h stall, 12h slow), the LLM considers
    context: torrent popularity, seed count, elapsed time, disk space.
    """

    NODE_NAME = "poll_download"
    SYSTEM_PROMPT = POLL_DOWNLOAD_SYSTEM
    ACTIONS = POLL_DOWNLOAD_ACTIONS
    MAX_LLM_CALLS = 2  # Usually just 1 call to decide
    TERMINAL_ACTIONS = {"done", "wait", "switch", "search_alt", "abort"}

    def __init__(self, qb_tool: BaseTool | None = None, **kwargs: Any):
        super().__init__(**kwargs)
        self.qb_tool = qb_tool or QBTool()
        self.health = TorrentHealth()

    def _build_prompt(self, context: dict[str, Any], state: dict[str, Any]) -> str:
        torrent_hash = state.get("torrent_hash", "")
        episode = state.get("episode_number", "?")

        # Get raw health data (not the decision, just the data)
        qb_status = context.get("qb_status", {})
        health_eval = context.get("health_eval", {})

        progress = qb_status.get("progress", 0.0) * 100
        speed = qb_status.get("download_speed", 0)
        state_name = health_eval.get("state", "unknown")
        recommend = health_eval.get("recommend", "wait")
        reason = health_eval.get("reason", "")

        added_at = qb_status.get("added_at")
        elapsed = ""
        if added_at:
            try:
                added = datetime.fromisoformat(added_at)
                delta = datetime.now(UTC) - added
                elapsed = f"{delta.total_seconds() / 3600:.1f} 小时"
            except (ValueError, TypeError):
                elapsed = "未知"

        history = context.get("history", [])
        history_text = ""
        if history:
            history_text = "\n之前的操作：\n" + "\n".join(
                f"- {h['action']}: {h['result'][:100]}" for h in history
            )

        return (
            f"目标：第 {episode} 集\n"
            f"种子 hash：{torrent_hash[:12]}...\n"
            f"下载进度：{progress:.1f}%\n"
            f"下载速度：{speed / 1024:.1f} KB/s\n"
            f"健康状态：{state_name}\n"
            f"健康建议：{recommend}\n"
            f"原因：{reason}\n"
            f"已等待：{elapsed}\n"
            f"{history_text}\n\n"
            f"请决定下一步。"
        )

    async def _load_context(self, state: dict[str, Any]) -> dict[str, Any]:
        """Load qBittorrent status and health evaluation."""
        torrent_hash = state.get("torrent_hash")
        if not torrent_hash:
            ctx = {"qb_status": {}, "health_eval": {"state": "error", "recommend": "switch", "reason": "No torrent hash"}}
            state["_poll_context"] = ctx
            return ctx

        result = await self.qb_tool.invoke(
            QBToolInput(action="get_status", torrent_hash=torrent_hash)
        )
        if not result.success:
            ctx = {"qb_status": {}, "health_eval": {"state": "error", "recommend": "switch", "reason": result.error}}
            state["_poll_context"] = ctx
            return ctx

        qb_status = result.data.get("status", {})
        health_eval = self.health.evaluate(qb_status)
        ctx = {"qb_status": qb_status, "health_eval": health_eval}
        state["_poll_context"] = ctx
        return ctx

    async def _act(self, action: Any, state: dict[str, Any]) -> dict[str, Any]:
        if action.type == "switch":
            torrent_hash = state.get("torrent_hash")
            if torrent_hash:
                await self._delete_torrent(torrent_hash)
            return {"success": True, "output": "Torrent deleted"}

        if action.type == "check_system":
            # Use Bash to check disk space and qB status
            import platform
            if platform.system() == "Windows":
                cmd = "wmic logicaldisk where DeviceID='C:' get FreeSpace,Size /format:csv"
            else:
                cmd = "df -h /"
            result = await self.bash_tool.invoke(BashToolInput(command=cmd))
            return {
                "success": result.success,
                "output": result.data.get("stdout", "")[:1000] if result.success else result.error,
            }

        return await super()._act(action, state)

    def _build_result(self, action: Any, result: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
        poll_ctx = state.get("_poll_context", {})
        qb_status = poll_ctx.get("qb_status", {})

        if action.type == "done":
            content_path = qb_status.get("content_path") or qb_status.get("save_path")
            content_path = self._map_remote_path(content_path)
            download_files = [content_path] if content_path else []
            return {
                "status": "downloaded",
                "download_progress": 1.0,
                "download_files": download_files,
                "torrent_name": qb_status.get("name"),
            }

        if action.type == "switch":
            failed_hashes = list(state.get("torrent_failed_hashes", []))
            torrent_hash = state.get("torrent_hash")
            if torrent_hash and torrent_hash not in failed_hashes:
                failed_hashes.append(torrent_hash)
            return {
                "status": "retry_match",
                "torrent_failed_hashes": failed_hashes,
                "matched_torrent": None,
                "torrent_hash": None,
            }

        if action.type == "wait":
            interval = action.params.get("interval", 600)
            resume_after = (datetime.now(UTC) + timedelta(seconds=interval)).isoformat()
            return {
                "status": "downloading",
                "download_progress": qb_status.get("progress", 0.0),
                "resume_after": resume_after,
            }

        if action.type == "search_alt":
            # Delete was already done in _act, just return retry
            failed_hashes = list(state.get("torrent_failed_hashes", []))
            torrent_hash = state.get("torrent_hash")
            if torrent_hash and torrent_hash not in failed_hashes:
                failed_hashes.append(torrent_hash)
            return {
                "status": "retry_match",
                "torrent_failed_hashes": failed_hashes,
                "matched_torrent": None,
                "torrent_hash": None,
            }

        # Default: wait with standard interval
        interval = settings.check_interval_seconds or 600
        resume_after = (datetime.now(UTC) + timedelta(seconds=interval)).isoformat()
        return {
            "status": "downloading",
            "download_progress": qb_status.get("progress", 0.0),
            "resume_after": resume_after,
        }

    def _map_remote_path(self, path: str | None) -> str | None:
        if not path:
            return path
        remote_prefix = settings.qb_path_map_remote
        local_prefix = settings.qb_path_map_local
        if not remote_prefix or not local_prefix:
            return path
        norm_path = path.replace("/", "\\")
        norm_remote = remote_prefix.replace("/", "\\")
        if norm_path.startswith(norm_remote):
            return local_prefix + norm_path[len(norm_remote):]
        return path

    async def _delete_torrent(self, torrent_hash: str) -> None:
        try:
            delete_result = await self.qb_tool.invoke(
                QBToolInput(action="delete", torrent_hash=torrent_hash, delete_files=False)
            )
            if not delete_result.success:
                logger.warning("Failed to delete torrent {}: {}", torrent_hash, delete_result.error)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Exception while deleting torrent {}: {}", torrent_hash, exc)


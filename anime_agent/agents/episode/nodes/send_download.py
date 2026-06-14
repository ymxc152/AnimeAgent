"""send_download node — LLM-driven agent for adding torrents to qBittorrent."""

from typing import Any

from anime_agent.agents.episode.agent_prompts import SEND_DOWNLOAD_ACTIONS, SEND_DOWNLOAD_SYSTEM
from anime_agent.agents.episode.base_agent import BaseAgentNode
from anime_agent.tools.base import BaseTool
from anime_agent.tools.bash_tool import BashToolInput
from anime_agent.tools.qb_tool import QBTool, QBToolInput


class SendDownloadNode(BaseAgentNode):
    """LLM-driven download submission agent.

    Instead of just failing on qB errors, the agent diagnoses the issue
    and attempts recovery before giving up.
    """

    NODE_NAME = "send_download"
    SYSTEM_PROMPT = SEND_DOWNLOAD_SYSTEM
    ACTIONS = SEND_DOWNLOAD_ACTIONS
    MAX_LLM_CALLS = 2
    TERMINAL_ACTIONS = {"add", "abort"}

    def __init__(self, qb_tool: BaseTool | None = None, **kwargs: Any):
        super().__init__(**kwargs)
        self.qb_tool = qb_tool or QBTool()

    def _build_prompt(self, context: dict[str, Any], state: dict[str, Any]) -> str:
        matched = state.get("matched_torrent", {})
        failed_hashes = state.get("torrent_failed_hashes", [])
        episode = state.get("episode_number", "?")

        history = context.get("history", [])
        history_text = ""
        if history:
            history_text = "\n之前的操作：\n" + "\n".join(
                f"- {h['action']}: {h['result'][:100]}" for h in history
            )

        return (
            f"目标：下载第 {episode} 集\n"
            f"种子信息：hash={matched.get('info_hash', '?')[:12]}... "
            f"title={matched.get('title', '?')[:50]}\n"
            f"下载链接：{matched.get('link', '无')[:80]}\n"
            f"已失败 hash：{failed_hashes}\n"
            f"{history_text}\n\n"
            f"请决定如何添加下载。"
        )

    async def _act(self, action: Any, state: dict[str, Any]) -> dict[str, Any]:
        if action.type == "add":
            return await self._execute_add(state)
        if action.type == "check_qb":
            import platform
            if platform.system() == "Windows":
                cmd = "tasklist /fi \"imagename eq qbittorrent.exe\" 2>nul"
            else:
                cmd = "pgrep -a qbittorrent"
            result = await self.bash_tool.invoke(BashToolInput(command=cmd))
            return {
                "success": result.success,
                "output": result.data.get("stdout", "")[:500] if result.success else result.error,
            }
        return await super()._act(action, state)

    async def _execute_add(self, state: dict[str, Any]) -> dict[str, Any]:
        """Execute adding torrent to qBittorrent."""
        matched = state.get("matched_torrent")
        if not matched:
            return {"success": False, "output": "No matched torrent"}

        info_hash = matched.get("info_hash")
        if info_hash and info_hash in state.get("torrent_failed_hashes", []):
            return {"success": False, "output": f"Torrent {info_hash} already failed"}

        link = matched.get("link") or matched.get("magnet_url")
        if not link:
            return {"success": False, "output": "No download link"}

        result = await self.qb_tool.invoke(QBToolInput(action="add", torrent_url=link))
        if not result.success:
            return {"success": False, "output": f"qBittorrent error: {result.error}"}

        return {"success": True, "output": "Torrent added", "hash": result.data.get("hash", info_hash)}

    def _build_result(self, action: Any, result: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
        matched = state.get("matched_torrent", {})
        if action.type == "add" and result.get("success"):
            return {
                "status": "downloading",
                "torrent_hash": result.get("hash", matched.get("info_hash")),
                "torrent_name": matched.get("title"),
            }
        if action.type == "abort":
            failed_hashes = list(state.get("torrent_failed_hashes", []))
            info_hash = matched.get("info_hash")
            if info_hash and info_hash not in failed_hashes:
                failed_hashes.append(info_hash)
            return {
                "status": "failed",
                "errors": [f"Download failed: {result.get('output', 'Unknown')}"],
                "torrent_failed_hashes": failed_hashes,
            }
        return {"status": "failed", "errors": [result.get("output", "Download failed")]}


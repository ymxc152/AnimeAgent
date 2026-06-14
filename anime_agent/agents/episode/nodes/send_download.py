"""send_download node — LLM-driven agent for adding torrents to qBittorrent."""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from anime_agent.agents.episode.agent_prompts import SEND_DOWNLOAD_ACTIONS, SEND_DOWNLOAD_SYSTEM
from anime_agent.agents.episode.base_agent import BaseAgentNode
from anime_agent.memory.store import Store
from anime_agent.tools.base import BaseTool
from anime_agent.tools.bash_tool import BashToolInput
from anime_agent.tools.qb_tool import QBTool, QBToolInput
from anime_agent.utils.logger import logger


class SendDownloadNode(BaseAgentNode):
    """LLM-driven download submission agent.

    Instead of just failing on qB errors, the agent diagnoses the issue
    and attempts recovery before giving up.
    """

    NODE_NAME = "send_download"
    SYSTEM_PROMPT = SEND_DOWNLOAD_SYSTEM
    ACTIONS = SEND_DOWNLOAD_ACTIONS
    MAX_LLM_CALLS = 3
    TERMINAL_ACTIONS = {"add", "abort"}

    def __init__(
        self,
        qb_tool: BaseTool | None = None,
        session_factory: async_sessionmaker[AsyncSession] | None = None,
        **kwargs: Any,
    ):
        super().__init__(**kwargs)
        self.qb_tool = qb_tool or QBTool()
        self.session_factory = session_factory

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
                cmd = 'tasklist /fi "imagename eq qbittorrent.exe" 2>nul'
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
        failed_hashes = list(state.get("torrent_failed_hashes", []))

        if info_hash and info_hash in failed_hashes:
            return {"success": False, "output": f"Torrent {info_hash} already failed"}

        # Cross-subscription deduplication: refuse to reuse a hash already
        # assigned to another subscription's episode.
        duplicate = await self._find_duplicate_owner(state, info_hash)
        if duplicate:
            logger.warning(
                "Torrent hash {} already used by subscription {} episode {}; skipping",
                info_hash,
                duplicate.subscription_id,
                duplicate.episode_number,
            )
            return {
                "success": False,
                "output": (
                    f"Torrent {info_hash} already used by subscription {duplicate.subscription_id}"
                ),
            }

        link = matched.get("link") or matched.get("magnet_url")
        if not link:
            return {"success": False, "output": "No download link"}

        result = await self.qb_tool.invoke(QBToolInput(action="add", torrent_url=link))
        if not result.success:
            return {"success": False, "output": f"qBittorrent error: {result.error}"}

        return {
            "success": True,
            "output": "Torrent added",
            "hash": result.data.get("hash", info_hash),
        }

    async def _find_duplicate_owner(
        self, state: dict[str, Any], info_hash: str | None
    ) -> Any | None:
        """Return the Episode row that already owns this hash, if any."""
        if not info_hash or not self.session_factory:
            return None

        current_subscription = state.get("subscription_id")
        async with self.session_factory() as session:
            store = Store(session)
            existing = await store.episodes.get_by_torrent_hash(info_hash)
            if existing and existing.subscription_id != current_subscription:
                return existing
        return None

    def _build_result(
        self, action: Any, result: dict[str, Any], state: dict[str, Any]
    ) -> dict[str, Any]:
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
                "_error_handler_node": self.NODE_NAME,
            }

        # Treat any non-success add as a retry_match so the matcher can pick
        # another candidate, and mark the failed hash.
        failed_hashes = list(state.get("torrent_failed_hashes", []))
        info_hash = matched.get("info_hash")
        if info_hash and info_hash not in failed_hashes:
            failed_hashes.append(info_hash)
        return {
            "status": "retry_match",
            "errors": [result.get("output", "Download failed")],
            "torrent_failed_hashes": failed_hashes,
            "matched_torrent": None,
            "torrent_hash": None,
        }

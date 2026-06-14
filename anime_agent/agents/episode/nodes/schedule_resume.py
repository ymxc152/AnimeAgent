"""schedule_resume node for Episode Graph."""

from datetime import UTC, datetime, timedelta
from typing import Any

from anime_agent.agents.episode.agent_prompts import SCHEDULE_RESUME_ACTIONS, SCHEDULE_RESUME_SYSTEM
from anime_agent.agents.episode.base_agent import BaseAgentNode
from anime_agent.config import settings


class ScheduleResumeNode(BaseAgentNode):
    """LLM-driven scheduling agent.

    Decides optimal retry interval based on context:
    - Episode freshness, retry count, past errors.
    """

    NODE_NAME = "schedule_resume"
    SYSTEM_PROMPT = SCHEDULE_RESUME_SYSTEM
    ACTIONS = SCHEDULE_RESUME_ACTIONS
    MAX_LLM_CALLS = 1
    TERMINAL_ACTIONS = {"schedule"}

    def __init__(
        self,
        interval_seconds: int | None = None,
        rss_wait_seconds: int | None = None,
        **kwargs: Any,
    ):
        super().__init__(**kwargs)
        self.interval_seconds = interval_seconds or settings.check_interval_seconds
        self.rss_wait_seconds = rss_wait_seconds or settings.rss_wait_interval_seconds

    def _build_prompt(self, context: dict[str, Any], state: dict[str, Any]) -> str:
        prior_status = state.get("status", "")
        episode = state.get("episode_number", "?")
        existing_resume = state.get("resume_after")

        return (
            f"目标：决定第 {episode} 集的重试间隔\n"
            f"当前状态：{prior_status}\n"
            f"已有 resume_after：{existing_resume or '无'}\n"
            f"默认间隔：{self.interval_seconds}s\n"
            f"RSS 等待间隔：{self.rss_wait_seconds}s\n"
            f"请决定重试间隔（秒）。"
        )

    def _build_result(self, action: Any, result: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
        prior_status = state.get("status", "")
        existing_resume_after = state.get("resume_after")

        # Preserve adaptive resume_after for active downloads
        if existing_resume_after and prior_status == "downloading":
            return {"resume_after": existing_resume_after}

        interval = action.params.get("interval", self.interval_seconds)
        if prior_status in ("waiting_for_rss", "no_match"):
            interval = max(interval, self.rss_wait_seconds)

        resume_after = (datetime.now(UTC) + timedelta(seconds=interval)).isoformat()
        return {"resume_after": resume_after}


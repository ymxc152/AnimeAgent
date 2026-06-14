"""High-level data access layer."""

from datetime import datetime
from typing import Any, cast

from sqlalchemy import select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from anime_agent.memory.models import (
    AutoSubscribeRule,
    ChatMessage,
    Episode,
    ErrorLog,
    RSSSource,
    Subscription,
    TaskSchedule,
    UserRequest,
)


class SubscriptionStore:
    """Data access for Subscriptions."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, subscription: Subscription) -> Subscription:
        self.session.add(subscription)
        await self.session.commit()
        await self.session.refresh(subscription)
        return subscription

    async def get_by_id(self, subscription_id: int) -> Subscription | None:
        return await self.session.get(Subscription, subscription_id)

    async def get_by_bangumi_id(self, bangumi_id: int) -> Subscription | None:
        result = await self.session.execute(
            select(Subscription).where(Subscription.bangumi_id == bangumi_id)
        )
        return result.scalar_one_or_none()

    async def get_by_anilist_id(self, anilist_id: int) -> Subscription | None:
        result = await self.session.execute(
            select(Subscription).where(Subscription.anilist_id == anilist_id)
        )
        return result.scalar_one_or_none()

    async def list_active(self) -> list[Subscription]:
        result = await self.session.execute(
            select(Subscription).where(Subscription.status == "ongoing")
        )
        return list(result.scalars().all())

    async def list_auto_download_enabled(self) -> list[Subscription]:
        result = await self.session.execute(
            select(Subscription).where(
                Subscription.status == "ongoing",
                Subscription.auto_download_enabled.is_(True),
            )
        )
        return list(result.scalars().all())

    async def update(self, subscription: Subscription) -> Subscription:
        await self.session.commit()
        await self.session.refresh(subscription)
        return subscription

    async def toggle_auto_download(self, subscription_id: int, enabled: bool) -> bool:
        result = await self.session.execute(
            update(Subscription)
            .where(Subscription.id == subscription_id)
            .values(auto_download_enabled=enabled)
        )
        cursor_result = cast(CursorResult[Any], result)
        await self.session.commit()
        return cursor_result.rowcount > 0


class EpisodeStore:
    """Data access for Episodes."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, episode: Episode) -> Episode:
        self.session.add(episode)
        await self.session.commit()
        await self.session.refresh(episode)
        return episode

    async def get_by_subscription_and_number(
        self, subscription_id: int, episode_number: int
    ) -> Episode | None:
        result = await self.session.execute(
            select(Episode).where(
                Episode.subscription_id == subscription_id,
                Episode.episode_number == episode_number,
            )
        )
        return result.scalar_one_or_none()

    async def list_by_subscription(self, subscription_id: int) -> list[Episode]:
        result = await self.session.execute(
            select(Episode)
            .where(Episode.subscription_id == subscription_id)
            .order_by(Episode.episode_number)
        )
        return list(result.scalars().all())

    async def list_pending(self) -> list[Episode]:
        result = await self.session.execute(
            select(Episode).where(Episode.status == "pending").order_by(Episode.created_at)
        )
        return list(result.scalars().all())

    async def list_by_statuses(self, statuses: list[str]) -> list[Episode]:
        result = await self.session.execute(
            select(Episode).where(Episode.status.in_(statuses)).order_by(Episode.created_at)
        )
        return list(result.scalars().all())

    async def get_by_torrent_hash(self, torrent_hash: str) -> Episode | None:
        result = await self.session.execute(
            select(Episode).where(Episode.torrent_hash == torrent_hash)
        )
        return result.scalar_one_or_none()

    async def update(self, episode: Episode) -> Episode:
        await self.session.commit()
        await self.session.refresh(episode)
        return episode


class TaskScheduleStore:
    """Data access for TaskSchedules."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, schedule: TaskSchedule) -> TaskSchedule:
        self.session.add(schedule)
        await self.session.commit()
        await self.session.refresh(schedule)
        return schedule

    async def get_by_subscription(self, subscription_id: int) -> TaskSchedule | None:
        result = await self.session.execute(
            select(TaskSchedule).where(TaskSchedule.subscription_id == subscription_id)
        )
        return result.scalar_one_or_none()

    async def list_due(self, before: datetime) -> list[TaskSchedule]:
        result = await self.session.execute(
            select(TaskSchedule).where(
                TaskSchedule.is_active.is_(True),
                TaskSchedule.next_run_at <= before,
            )
        )
        return list(result.scalars().all())

    async def update_next_run(self, schedule_id: int, next_run_at: datetime) -> None:
        await self.session.execute(
            update(TaskSchedule)
            .where(TaskSchedule.id == schedule_id)
            .values(last_run_at=datetime.utcnow(), next_run_at=next_run_at)
        )
        await self.session.commit()


class UserRequestStore:
    """Data access for UserRequests."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, request: UserRequest) -> UserRequest:
        self.session.add(request)
        await self.session.commit()
        await self.session.refresh(request)
        return request

    async def get_by_id(self, request_id: int) -> UserRequest | None:
        return await self.session.get(UserRequest, request_id)

    async def update(self, request: UserRequest) -> UserRequest:
        await self.session.commit()
        await self.session.refresh(request)
        return request


class RSSSourceStore:
    """Data access for RSS sources."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, source: RSSSource) -> RSSSource:
        self.session.add(source)
        await self.session.commit()
        await self.session.refresh(source)
        return source

    async def get_by_id(self, source_id: int) -> RSSSource | None:
        return await self.session.get(RSSSource, source_id)

    async def list_all(self) -> list[RSSSource]:
        result = await self.session.execute(select(RSSSource).order_by(RSSSource.name))
        return list(result.scalars().all())

    async def list_active(self) -> list[RSSSource]:
        result = await self.session.execute(
            select(RSSSource).where(RSSSource.is_active.is_(True)).order_by(RSSSource.name)
        )
        return list(result.scalars().all())

    async def update(self, source: RSSSource) -> RSSSource:
        await self.session.commit()
        await self.session.refresh(source)
        return source

    async def delete(self, source: RSSSource) -> None:
        await self.session.delete(source)
        await self.session.commit()


class AutoSubscribeRuleStore:
    """Data access for auto-subscribe rules."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, rule: AutoSubscribeRule) -> AutoSubscribeRule:
        self.session.add(rule)
        await self.session.commit()
        await self.session.refresh(rule)
        return rule

    async def get_by_id(self, rule_id: int) -> AutoSubscribeRule | None:
        return await self.session.get(AutoSubscribeRule, rule_id)

    async def list_all(self) -> list[AutoSubscribeRule]:
        result = await self.session.execute(
            select(AutoSubscribeRule).order_by(AutoSubscribeRule.created_at.desc())
        )
        return list(result.scalars().all())

    async def list_enabled(self) -> list[AutoSubscribeRule]:
        result = await self.session.execute(
            select(AutoSubscribeRule)
            .where(AutoSubscribeRule.enabled.is_(True))
            .order_by(AutoSubscribeRule.created_at.desc())
        )
        return list(result.scalars().all())

    async def update(self, rule: AutoSubscribeRule) -> AutoSubscribeRule:
        await self.session.commit()
        await self.session.refresh(rule)
        return rule

    async def delete(self, rule: AutoSubscribeRule) -> None:
        await self.session.delete(rule)
        await self.session.commit()


class ChatMessageStore:
    """Data access for ChatMessage (conversation history)."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        session_id: str,
        role: str,
        content: str,
        intent_json: str | None = None,
        data_json: str | None = None,
    ) -> ChatMessage:
        msg = ChatMessage(
            session_id=session_id,
            role=role,
            content=content,
            intent_json=intent_json,
            data_json=data_json,
        )
        self.session.add(msg)
        await self.session.commit()
        await self.session.refresh(msg)
        return msg

    async def list_by_session(
        self, session_id: str, limit: int = 20
    ) -> list[ChatMessage]:
        result = await self.session.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.asc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def delete_session(self, session_id: str) -> None:
        result = await self.session.execute(
            select(ChatMessage).where(ChatMessage.session_id == session_id)
        )
        for msg in result.scalars().all():
            await self.session.delete(msg)
        await self.session.commit()


class ErrorLogStore:
    """Data access for error_logs table."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        episode_id: int,
        subscription_id: int,
        node_name: str,
        error_message: str = "",
        bash_commands_tried: str = "[]",
        llm_reasoning: str = "",
        resolution: str = "",
    ) -> ErrorLog:
        log = ErrorLog(
            episode_id=episode_id,
            subscription_id=subscription_id,
            node_name=node_name,
            error_message=error_message,
            bash_commands_tried=bash_commands_tried,
            llm_reasoning=llm_reasoning,
            resolution=resolution,
        )
        self.session.add(log)
        await self.session.flush()
        return log

    async def list_recent(self, episode_id: int, limit: int = 5) -> list[ErrorLog]:
        stmt = (
            select(ErrorLog)
            .where(ErrorLog.episode_id == episode_id)
            .order_by(ErrorLog.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())


class Store:
    """Combined store facade."""

    def __init__(self, session: AsyncSession):
        self.subscriptions = SubscriptionStore(session)
        self.episodes = EpisodeStore(session)
        self.schedules = TaskScheduleStore(session)
        self.user_requests = UserRequestStore(session)
        self.rss_sources = RSSSourceStore(session)
        self.auto_subscribe_rules = AutoSubscribeRuleStore(session)
        self.chat_messages = ChatMessageStore(session)
        self.error_logs = ErrorLogStore(session)

    async def __aenter__(self) -> "Store":
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        await self.subscriptions.session.close()

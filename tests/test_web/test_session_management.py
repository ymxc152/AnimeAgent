"""Tests for database session management and transaction handling."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from anime_agent.web import _create_subscription_from_payload
from anime_agent.web_schemas import SubscriptionCreateRequest


@pytest.fixture
def mock_db():
    """Create a mock database session."""
    db = AsyncMock(spec=AsyncSession)
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    db.flush = AsyncMock()
    db.refresh = AsyncMock()
    db.add = MagicMock()
    return db


@pytest.fixture
def sample_payload():
    """Create a sample subscription payload."""
    return SubscriptionCreateRequest(
        title_romaji="Sousou no Frieren",
        title_native="葬送のフリーレン",
        title_chinese="葬送的芙莉莲",
        bangumi_id=12345,
        anilist_id=None,
        season_year=2023,
        season="FALL",
        total_episodes=12,
    )


class TestTransactionHandling:
    """Test transaction handling in database operations."""

    async def test_commits_on_success(self, mock_db, sample_payload):
        """Should commit transaction on success."""
        with patch("anime_agent.web.Store") as mock_store_class, \
             patch("anime_agent.web.MetadataResolver") as mock_resolver_class:

            # Setup mocks
            mock_store = AsyncMock()
            mock_store_class.return_value = mock_store
            mock_store.subscriptions.get_by_bangumi_id.return_value = None

            mock_resolver = AsyncMock()
            mock_resolver_class.return_value = mock_resolver
            mock_resolver.get_details.return_value = MagicMock(
                success=True,
                data={"details": {"title_romaji": "Sousou no Frieren"}},
            )

            # Execute
            await _create_subscription_from_payload(mock_db, sample_payload, "manual")

            # Verify commit was called
            mock_db.commit.assert_called_once()
            mock_db.rollback.assert_not_called()

    async def test_continues_on_metadata_error(self, mock_db, sample_payload):
        """Should continue even when metadata resolution fails."""
        with patch("anime_agent.web.Store") as mock_store_class, \
             patch("anime_agent.web.MetadataResolver") as mock_resolver_class:

            # Setup mocks
            mock_store = AsyncMock()
            mock_store_class.return_value = mock_store
            mock_store.subscriptions.get_by_bangumi_id.return_value = None

            mock_resolver = AsyncMock()
            mock_resolver_class.return_value = mock_resolver
            mock_resolver.get_details.side_effect = Exception("Metadata service unavailable")

            # Execute - should not raise exception
            result = await _create_subscription_from_payload(mock_db, sample_payload, "manual")

            # Verify subscription was created with fallback values
            assert result is not None
            mock_db.commit.assert_called_once()

    async def test_returns_existing_subscription(self, mock_db, sample_payload):
        """Should return existing subscription without creating new one."""
        with patch("anime_agent.web.Store") as mock_store_class:
            # Setup mocks
            mock_store = AsyncMock()
            mock_store_class.return_value = mock_store

            existing_sub = MagicMock()
            existing_sub.id = 1
            existing_sub.title_romaji = "Sousou no Frieren"
            mock_store.subscriptions.get_by_bangumi_id.return_value = existing_sub

            # Execute
            result = await _create_subscription_from_payload(mock_db, sample_payload, "manual")

            # Verify
            assert result == existing_sub
            mock_db.commit.assert_not_called()
            mock_db.add.assert_not_called()

    async def test_creates_episodes_on_success(self, mock_db, sample_payload):
        """Should create episodes for the subscription."""
        with patch("anime_agent.web.Store") as mock_store_class, \
             patch("anime_agent.web.MetadataResolver") as mock_resolver_class:

            # Setup mocks
            mock_store = AsyncMock()
            mock_store_class.return_value = mock_store
            mock_store.subscriptions.get_by_bangumi_id.return_value = None

            mock_resolver = AsyncMock()
            mock_resolver_class.return_value = mock_resolver
            mock_resolver.get_details.return_value = MagicMock(
                success=True,
                data={"details": {"title_romaji": "Sousou no Frieren", "total_episodes": 12}},
            )

            # Execute
            await _create_subscription_from_payload(mock_db, sample_payload, "manual")

            # Verify episodes were created (12 episodes + 1 subscription + 1 schedule)
            assert mock_db.add.call_count == 14  # 1 subscription + 12 episodes + 1 schedule

    async def test_flush_before_adding_episodes(self, mock_db, sample_payload):
        """Should flush to get subscription ID before adding episodes."""
        with patch("anime_agent.web.Store") as mock_store_class, \
             patch("anime_agent.web.MetadataResolver") as mock_resolver_class:

            # Setup mocks
            mock_store = AsyncMock()
            mock_store_class.return_value = mock_store
            mock_store.subscriptions.get_by_bangumi_id.return_value = None

            mock_resolver = AsyncMock()
            mock_resolver_class.return_value = mock_resolver
            mock_resolver.get_details.return_value = MagicMock(
                success=True,
                data={"details": {"title_romaji": "Sousou no Frieren"}},
            )

            # Execute
            await _create_subscription_from_payload(mock_db, sample_payload, "manual")

            # Verify flush was called before adding episodes
            mock_db.flush.assert_called_once()

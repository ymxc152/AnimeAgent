"""Tests for DiscoveryService."""

from unittest.mock import MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from anime_agent.config import Settings
from anime_agent.services.discovery import DiscoveryService


@pytest.fixture
def service(db_session: AsyncSession) -> DiscoveryService:
    return DiscoveryService(
        session=db_session,
        resolver=MagicMock(),
        settings=Settings(),
    )


def test_infer_total_episodes_uses_metadata(service: DiscoveryService) -> None:
    assert service._infer_total_episodes({"total_episodes": 24}) == 24


def test_infer_total_episodes_movie_default(service: DiscoveryService) -> None:
    assert service._infer_total_episodes({"format": "Movie"}) == 1


def test_infer_total_episodes_ova_default(service: DiscoveryService) -> None:
    assert service._infer_total_episodes({"format": "OVA"}) == 1


def test_infer_total_episodes_config_default(service: DiscoveryService) -> None:
    assert service._infer_total_episodes({}) == service.settings.discovery_default_total_episodes

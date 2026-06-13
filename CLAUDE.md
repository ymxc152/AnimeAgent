# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AnimeAgent is a multi-agent anime episode tracking and downloading automation system built on LangGraph. It automates: broadcast detection, RSS intelligent matching, downloading, file organization/hard-linking, Emby media library refresh, and push notifications. Bangumi is the primary metadata source. The project is at MVP stage (v0.1.0); the conversational agent layer is not yet implemented.

The project is primarily in Chinese (README, comments, config, UI).

## Common Commands

### Backend (Python)

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run all mock tests (excludes real_data marker, with coverage)
pytest

# Run a single test file or test function
pytest tests/test_services/test_torrent_selector.py
pytest tests/test_services/test_torrent_selector.py::test_function_name

# Run tests that call real external APIs
pytest -m real_data

# Lint
ruff check anime_agent tests

# Format
ruff format

# Type-check (strict mode)
mypy anime_agent

# Run web panel only
uvicorn anime_agent.web:app --reload --host 0.0.0.0 --port 8000

# Run full app (scheduler + web panel)
python -m anime_agent.main
```

CLI entry point: `anime-agent` (registered via pyproject.toml `[project.scripts]`).

### Frontend (React + TypeScript)

```bash
cd frontend
npm run dev      # Vite dev server
npm run build    # TypeScript compile + Vite production build
npm run lint     # ESLint
npm run test     # Vitest
```

## Architecture

### Layered Design

The codebase follows a strict layered architecture (see CONTRIBUTING.md for full rules):

- **Tools** (`tools/`): External IO only, no business logic. Each inherits `BaseTool` with `invoke()` and `healthcheck()`.
- **Services** (`services/`): Business logic (torrent selection, metadata resolution, content filtering, scheduling).
- **Agents/Nodes** (`agents/episode/nodes/`): State orchestration and tool invocation only, no business logic.
- **Memory** (`memory/`): SQLAlchemy async ORM models and `Store` data access facade.

### Core Pipeline: Episode Graph

The central element is the `StateGraph` in `anime_agent/agents/episode/graph.py`. Each episode flows through:

```
START → status_router → [route based on episode status]
  → fetch_rss → match_torrent → send_download → poll_download → organize_files → refresh_emby → END
```

With branches to `human_review` (manual approval), `schedule_resume` (deferred retry), and `handle_error`.

- **EpisodeGraphRunner** (`agents/episode/runner.py`): Loads DB state, executes graph, persists results.
- **Scheduler** (`services/scheduler.py`): APScheduler-based; runs health checks on startup, ticks to process due episodes, weekly new-season discovery.

### Torrent Matching

`services/torrent_selector.py` uses rule-based pre-filtering (episode number regex, CJK/Latin keyword extraction, stop-word filtering) followed by LLM-based selection with confidence scoring. Low-confidence matches (after 3 attempts) go to `human_review`.

### Configuration

All config is environment-variable driven via Pydantic Settings in `anime_agent/config.py`. Copy `.env.example` to `.env` and fill in credentials for LLM, qBittorrent, Emby, TMDB, RSS feeds, media paths, filters, and notifications.

### Database

SQLite via SQLAlchemy async (aiosqlite). Seven ORM models in `memory/models.py`: Subscription, Episode, MetadataMapping, RSSSource, SystemConfig, UserRequest, TaskSchedule.

### Web Panel

FastAPI REST API in `anime_agent/web.py` with React 19 + TypeScript + Tailwind CSS frontend (`frontend/`). In production, built frontend is served as static files from `frontend/dist/`.

## Testing Conventions

- `asyncio_mode = "auto"` (pytest-asyncio) — no need for `@pytest.mark.asyncio` decorators.
- Tests use in-memory SQLite and mock external APIs by default.
- `tests/fakes/` contains test doubles for tools.
- `tests/test_real_data/` contains tests hitting real APIs, excluded by default (`-m 'not real_data'`).
- Pre-commit hooks run Ruff lint+format and MyPy.

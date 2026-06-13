"""Real-data test fixtures: restore production .env values for external services."""

from pathlib import Path

from anime_agent.config import settings


def _load_dotenv(path: Path) -> dict[str, str]:
    """Parse a simple KEY=VALUE .env file into a dict."""
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key] = value.strip().strip('"').strip("'")
    return values


# Restore .env values that the root conftest resets to local defaults.
_env = _load_dotenv(Path(__file__).parent.parent.parent / ".env")
for key in ("QB_HOST", "QB_USERNAME", "QB_PASSWORD", "EMBY_HOST", "EMBY_API_KEY"):
    if key in _env:
        attr = key.lower()
        setattr(settings, attr, _env[key])

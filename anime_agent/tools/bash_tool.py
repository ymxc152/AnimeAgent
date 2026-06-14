"""BashTool for executing shell commands with safety restrictions."""

import asyncio
import os
import platform
import re
import sys
from typing import Any

from anime_agent.tools.base import BaseTool, ToolInput, ToolOutput
from anime_agent.utils.logger import logger


class BashToolInput(ToolInput):
    """Input for BashTool."""

    command: str
    timeout: int = 90  # seconds


class BashTool(BaseTool):
    """Execute shell commands with safety restrictions for error diagnosis and repair.

    Features:
    - Subprocess isolation (no inherited environment variables)
    - Command blacklist (dangerous operations blocked)
    - Sensitive output filtering (API keys, passwords redacted)
    - Configurable timeout (default 90s)
    """

    name = "bash"
    description = "Execute shell commands for error diagnosis and repair."

    # ── Command blacklist ──────────────────────────────────────────────
    # Patterns that indicate dangerous or prohibited commands.
    _BLOCKED_PATTERNS: list[str] = [
        # Destructive filesystem
        r"rm\s+-rf\s+/",
        r"rm\s+-rf\s+~",
        r"rmdir\s+/[sS]",
        r"format\s+[a-zA-Z]:",
        r"mkfs\.",
        # System control
        r"\bshutdown\b",
        r"\breboot\b",
        r"\bhalt\b",
        r"\bpoweroff\b",
        # Permissions
        r"chmod\s+777",
        r"chown\s+.*\s+/",
        # Network exfiltration
        r"\bcurl\b",
        r"\bwget\b",
        r"\bnc\s+-",
        r"\bnetcat\b",
        r"\bnmap\b",
        r"\bssh\b",
        r"\bscp\b",
        r"\brsync\b.*:",
        r"\bftp\b",
        r"\bsftp\b",
        # Environment variable enumeration
        r"\benv\b",
        r"\bprintenv\b",
        r"\bset\b\s*$",
        r"\bexport\b\s+-p",
        # .env file access
        r"cat\s+\.env",
        r"type\s+\.env",
        r"more\s+\.env",
        r"less\s+\.env",
        r"head\s+.*\.env",
        r"tail\s+.*\.env",
        r"grep.*\.env",
        r"echo\s+\$[A-Z_]*KEY",
        r"echo\s+\$[A-Z_]*TOKEN",
        r"echo\s+\$[A-Z_]*PASSWORD",
        r"echo\s+\$[A-Z_]*SECRET",
        # Process manipulation
        r"\bkill\s+-9\s+1\b",
        r"\bkillall\b",
        r"\bpkill\b",
    ]

    # ── Sensitive output patterns ──────────────────────────────────────
    # Regex patterns for content that must be redacted from output.
    _SENSITIVE_PATTERNS: list[str] = [
        r"sk-[a-zA-Z0-9]{20,}",            # OpenAI-style API keys
        r"tp-[a-zA-Z0-9]{20,}",            # Token-plan keys
        r"ghp_[a-zA-Z0-9]{36}",            # GitHub tokens
        r"QB_PASSWORD=\S+",                 # qBittorrent password
        r"EMBY_API_KEY=\S+",               # Emby API key
        r"TMDB_API_KEY=\S+",               # TMDB API key
        r"TMDB_READ_ACCESS_TOKEN=\S+",     # TMDB token
        r"OPENAI_API_KEY=\S+",             # OpenAI key
        r"ANTHROPIC_API_KEY=\S+",          # Anthropic key
        r"APPRISE_URLS=\S+",               # Apprise notification URLs
        r"Bearer\s+[a-zA-Z0-9._-]{20,}",  # Bearer tokens
        r"Basic\s+[a-zA-Z0-9+/=]{20,}",   # Basic auth tokens
    ]

    # ── Safe environment variables ─────────────────────────────────────
    # Only these variables are passed to the subprocess.
    _SAFE_ENV_KEYS: set[str] = {
        "PATH", "HOME", "USERPROFILE", "SYSTEMROOT", "WINDIR",
        "COMSPEC", "SYSTEMDRIVE", "HOMEDRIVE", "HOMEPATH",
        "TEMP", "TMP", "TMPDIR",
        "OS_TYPE",  # Our custom OS indicator
        "LANG", "LC_ALL",
    }

    def __init__(self) -> None:
        self._compiled_blocked = [re.compile(p, re.IGNORECASE) for p in self._BLOCKED_PATTERNS]
        self._compiled_sensitive = [re.compile(p) for p in self._SENSITIVE_PATTERNS]
        self._os_type = self._detect_os()

    @staticmethod
    def _detect_os() -> str:
        """Detect the operating system type."""
        return platform.system()  # "Windows" or "Linux"

    def _build_safe_env(self) -> dict[str, str]:
        """Build a minimal environment dict with only safe variables."""
        safe_env: dict[str, str] = {}
        current_env = os.environ
        for key in self._SAFE_ENV_KEYS:
            if key in current_env:
                safe_env[key] = current_env[key]
        # Always include OS_TYPE
        safe_env["OS_TYPE"] = self._os_type
        return safe_env

    def _is_blocked(self, command: str) -> bool:
        """Check if a command matches any blocked pattern."""
        return any(pattern.search(command) for pattern in self._compiled_blocked)

    def _filter_output(self, text: str) -> str:
        """Replace sensitive content in output with [REDACTED]."""
        filtered = text
        for pattern in self._compiled_sensitive:
            filtered = pattern.sub("[REDACTED]", filtered)
        return filtered

    async def invoke(self, input_data: ToolInput) -> ToolOutput:
        """Execute a shell command with safety restrictions."""
        bash_input = BashToolInput.model_validate(input_data)
        command = bash_input.command.strip()

        if not command:
            return ToolOutput(success=False, error="Empty command")

        # ── Step 1: Command blacklist check ──
        if self._is_blocked(command):
            logger.warning("Blocked dangerous command: {}", command[:100])
            return ToolOutput(
                success=False,
                error=f"Command blocked by safety policy: {command[:100]}...",
            )

        # ── Step 2: Build safe environment ──
        safe_env = self._build_safe_env()

        # ── Step 3: Choose shell based on OS ──
        if self._os_type == "Windows":
            shell_cmd = ["cmd.exe", "/c", command]
        else:
            shell_cmd = ["sh", "-c", command]

        # ── Step 4: Execute with timeout ──
        try:
            subprocess_kwargs: dict[str, Any] = {
                "stdout": asyncio.subprocess.PIPE,
                "stderr": asyncio.subprocess.PIPE,
                "env": safe_env,
            }
            if sys.platform == "win32":
                subprocess_kwargs["creationflags"] = 0x08000000

            process = await asyncio.create_subprocess_exec(
                *shell_cmd,
                **subprocess_kwargs,
            )

            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                process.communicate(),
                timeout=bash_input.timeout,
            )

            stdout_raw = stdout_bytes.decode("utf-8", errors="replace")
            stderr_raw = stderr_bytes.decode("utf-8", errors="replace")

            # ── Step 5: Filter sensitive content ──
            stdout_filtered = self._filter_output(stdout_raw)
            stderr_filtered = self._filter_output(stderr_raw)

            return_code = process.returncode or 0
            success = return_code == 0

            return ToolOutput(
                success=success,
                data={
                    "stdout": stdout_filtered[:10000],  # Cap output size
                    "stderr": stderr_filtered[:5000],
                    "return_code": return_code,
                    "os_type": self._os_type,
                },
                error="" if success else f"Command exited with code {return_code}",
            )

        except TimeoutError:
            # Kill the process on timeout
            try:
                process.kill()
                await process.wait()
            except ProcessLookupError:
                pass
            logger.warning("Command timed out after {}s: {}", bash_input.timeout, command[:100])
            return ToolOutput(
                success=False,
                error=f"Command timed out after {bash_input.timeout}s",
            )
        except OSError as exc:
            logger.error("Failed to execute command: {}", exc)
            return ToolOutput(success=False, error=f"Failed to execute: {exc}")

    async def healthcheck(self) -> ToolOutput:
        """Check that shell is available."""
        try:
            if self._os_type == "Windows":
                process = await asyncio.create_subprocess_exec(
                    "cmd.exe", "/c", "echo ok",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
            else:
                process = await asyncio.create_subprocess_exec(
                    "sh", "-c", "echo ok",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
            await asyncio.wait_for(process.communicate(), timeout=5)
            return ToolOutput(success=True, data={"status": "ok", "os_type": self._os_type})
        except Exception as exc:
            return ToolOutput(success=False, error=f"Shell not available: {exc}")

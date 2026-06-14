"""Tests for BashTool — security, execution, and output filtering."""

import pytest

from anime_agent.tools.bash_tool import BashTool, BashToolInput


@pytest.fixture
def tool():
    return BashTool()


# ── Command blacklist ───────────────────────────────────────────────────


class TestCommandBlacklist:
    async def test_blocks_rm_rf_root(self, tool):
        result = await tool.invoke(BashToolInput(command="rm -rf /"))
        assert not result.success
        assert "blocked" in result.error.lower()

    async def test_blocks_rm_rf_home(self, tool):
        result = await tool.invoke(BashToolInput(command="rm -rf ~"))
        assert not result.success
        assert "blocked" in result.error.lower()

    async def test_blocks_shutdown(self, tool):
        result = await tool.invoke(BashToolInput(command="shutdown -h now"))
        assert not result.success

    async def test_blocks_reboot(self, tool):
        result = await tool.invoke(BashToolInput(command="reboot"))
        assert not result.success

    async def test_blocks_curl(self, tool):
        result = await tool.invoke(BashToolInput(command="curl http://evil.com"))
        assert not result.success

    async def test_blocks_wget(self, tool):
        result = await tool.invoke(BashToolInput(command="wget http://evil.com"))
        assert not result.success

    async def test_blocks_ssh(self, tool):
        result = await tool.invoke(BashToolInput(command="ssh user@host"))
        assert not result.success

    async def test_blocks_env_read(self, tool):
        result = await tool.invoke(BashToolInput(command="env"))
        assert not result.success

    async def test_blocks_dotenv_read(self, tool):
        result = await tool.invoke(BashToolInput(command="cat .env"))
        assert not result.success

    async def test_blocks_chmod_777(self, tool):
        result = await tool.invoke(BashToolInput(command="chmod 777 /tmp"))
        assert not result.success

    async def test_blocks_kill_init(self, tool):
        result = await tool.invoke(BashToolInput(command="kill -9 1"))
        assert not result.success

    async def test_blocks_echo_api_key_var(self, tool):
        result = await tool.invoke(BashToolInput(command="echo $OPENAI_API_KEY"))
        assert not result.success

    async def test_blocks_nmap(self, tool):
        result = await tool.invoke(BashToolInput(command="nmap -sV 192.168.1.1"))
        assert not result.success


# ── Safe commands ───────────────────────────────────────────────────────


class TestSafeCommands:
    async def test_allows_echo(self, tool):
        result = await tool.invoke(BashToolInput(command="echo hello"))
        assert result.success
        assert "hello" in result.data["stdout"]

    async def test_allows_dir_or_ls(self, tool):
        # Use a safe read-only command
        import platform
        cmd = "dir" if platform.system() == "Windows" else "ls"
        result = await tool.invoke(BashToolInput(command=cmd))
        assert result.success

    async def test_empty_command_returns_error(self, tool):
        result = await tool.invoke(BashToolInput(command=""))
        assert not result.success
        assert "empty" in result.error.lower()

    async def test_whitespace_command_returns_error(self, tool):
        result = await tool.invoke(BashToolInput(command="   "))
        assert not result.success


# ── Sensitive output filtering ──────────────────────────────────────────


class TestSensitiveOutputFiltering:
    def test_filters_openai_key(self, tool):
        output = tool._filter_output("key=sk-abcdefghijklmnopqrstuvwxyz123456")
        assert "REDACTED" in output
        assert "sk-" not in output

    def test_filters_github_token(self, tool):
        output = tool._filter_output("token=ghp_abcdefghijklmnopqrstuvwxyz1234567890")
        assert "REDACTED" in output
        assert "ghp_" not in output

    def test_filters_bearer_token(self, tool):
        output = tool._filter_output("Authorization: Bearer abcdefghijklmnopqrst")
        assert "REDACTED" in output

    def test_filters_qb_password(self, tool):
        output = tool._filter_output("QB_PASSWORD=supersecret123")
        assert "REDACTED" in output

    def test_filters_emby_api_key(self, tool):
        output = tool._filter_output("EMBY_API_KEY=abcdef123456")
        assert "REDACTED" in output

    def test_preserves_normal_output(self, tool):
        normal = "total 42\ndrwxr-xr-x  5 user user 4096 Jan  1 00:00 ."
        assert tool._filter_output(normal) == normal


# ── Safe environment ────────────────────────────────────────────────────


class TestSafeEnvironment:
    def test_build_safe_env_contains_path(self, tool):
        env = tool._build_safe_env()
        assert "PATH" in env

    def test_build_safe_env_contains_os_type(self, tool):
        env = tool._build_safe_env()
        assert "OS_TYPE" in env

    def test_build_safe_env_excludes_secrets(self, tool):
        env = tool._build_safe_env()
        for key in env:
            assert key in BashTool._SAFE_ENV_KEYS


# ── Healthcheck ─────────────────────────────────────────────────────────


class TestBashToolHealthcheck:
    async def test_healthcheck_returns_ok(self, tool):
        result = await tool.healthcheck()
        assert result.success
        assert result.data["status"] == "ok"

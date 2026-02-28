import pytest

from core.config import load_config
from core.types import RiskLevel, ToolCall
from tools import register_all_tools
from tools.executor import ToolExecutor


@pytest.fixture
def executor():
    config = load_config()
    ex = ToolExecutor(config.tools)
    register_all_tools(ex, config)
    return ex


def test_risk_safe(executor):
    tc = ToolCall(id="1", name="list_directory", args={"path": "/tmp"})
    assert executor.classify_risk(tc) == RiskLevel.SAFE


def test_risk_moderate(executor):
    tc = ToolCall(id="2", name="write_file", args={"path": "/tmp/x", "content": "hi"})
    assert executor.classify_risk(tc) == RiskLevel.MODERATE


def test_risk_dangerous_rm(executor):
    tc = ToolCall(id="3", name="run_shell", args={"command": "rm -rf /"})
    assert executor.classify_risk(tc) == RiskLevel.DANGEROUS


def test_risk_dangerous_blocked(executor):
    tc = ToolCall(id="3b", name="run_shell", args={"command": "mkfs.ext4 /dev/sda"})
    assert executor.classify_risk(tc) == RiskLevel.DANGEROUS


def test_risk_dangerous_kill(executor):
    tc = ToolCall(id="4", name="kill_process", args={"pid": 1})
    assert executor.classify_risk(tc) == RiskLevel.DANGEROUS


def test_risk_unknown_defaults_moderate(executor):
    tc = ToolCall(id="4b", name="some_future_tool", args={})
    assert executor.classify_risk(tc) == RiskLevel.MODERATE


def test_risk_shell_safe_command(executor):
    tc = ToolCall(id="4c", name="run_shell", args={"command": "echo hello"})
    assert executor.classify_risk(tc) == RiskLevel.MODERATE


@pytest.mark.asyncio
async def test_unknown_tool(executor):
    tc = ToolCall(id="5", name="nonexistent_tool", args={})
    result = await executor.execute(tc)
    assert result.is_error
    assert "Unknown tool" in result.content


@pytest.mark.asyncio
async def test_shell_echo(executor):
    tc = ToolCall(id="6", name="run_shell", args={"command": "echo hello"})
    result = await executor.execute(tc)
    assert "hello" in result.content
    assert not result.is_error


@pytest.mark.asyncio
async def test_list_directory(executor):
    tc = ToolCall(id="7", name="list_directory", args={"path": "/tmp"})
    result = await executor.execute(tc)
    assert not result.is_error


@pytest.mark.asyncio
async def test_write_read_file(executor, tmp_path):
    path = str(tmp_path / "test.txt")
    write_tc = ToolCall(id="8", name="write_file", args={"path": path, "content": "hello world"})
    result = await executor.execute(write_tc)
    assert not result.is_error
    assert "Written" in result.content

    read_tc = ToolCall(id="9", name="read_file", args={"path": path})
    result = await executor.execute(read_tc)
    assert "hello world" in result.content


@pytest.mark.asyncio
async def test_search_files(executor, tmp_path):
    (tmp_path / "foo.txt").write_text("x")
    (tmp_path / "bar.py").write_text("y")
    tc = ToolCall(id="9b", name="search_files", args={"pattern": "*.py", "path": str(tmp_path)})
    result = await executor.execute(tc)
    assert "bar.py" in result.content


@pytest.mark.asyncio
async def test_shell_timeout(executor):
    tc = ToolCall(id="10", name="run_shell", args={"command": "sleep 60", "timeout": 2})
    result = await executor.execute(tc)
    assert "timed out" in result.content.lower()


@pytest.mark.asyncio
async def test_list_processes(executor):
    tc = ToolCall(id="11", name="list_processes", args={})
    result = await executor.execute(tc)
    assert "PID" in result.content
    assert not result.is_error


@pytest.mark.asyncio
async def test_output_truncation(executor):
    # Generate output longer than output_max_chars (4096 in default config)
    tc = ToolCall(id="12", name="run_shell", args={"command": "python3 -c \"print('x' * 5000)\""})
    result = await executor.execute(tc)
    assert "truncated" in result.content


@pytest.mark.asyncio
async def test_dangerous_blocked_by_confirm(executor):
    """Dangerous ops with confirm callback that denies should return cancelled."""

    async def deny(_tc):
        return False

    executor.on_confirm_request = deny
    tc = ToolCall(id="13", name="kill_process", args={"pid": 99999})
    result = await executor.execute(tc)
    assert "cancelled" in result.content.lower()

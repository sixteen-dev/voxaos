from unittest.mock import AsyncMock, MagicMock

import pytest

from core.config import load_config
from core.context import ContextManager


def test_context_manager_add_turn():
    ctx = ContextManager(max_history=5)
    ctx.add_turn("user", "hello")
    ctx.add_turn("assistant", "hi")
    msgs = ctx.get_messages()
    assert len(msgs) == 2
    assert msgs[0]["role"] == "user"
    assert msgs[1]["role"] == "assistant"


def test_context_manager_trim():
    ctx = ContextManager(max_history=3)
    for i in range(10):
        ctx.add_turn("user", f"msg {i}")
        ctx.add_turn("assistant", f"resp {i}")
    msgs = ctx.get_messages()
    assert len(msgs) <= 6  # max_history * 2


def test_context_manager_clear():
    ctx = ContextManager()
    ctx.add_turn("user", "test")
    ctx.clear()
    assert len(ctx.get_messages()) == 0


def test_context_manager_message_format():
    ctx = ContextManager()
    ctx.add_turn("user", "what time is it")
    ctx.add_turn("assistant", "it's 3pm")
    msgs = ctx.get_messages()
    assert msgs[0] == {"role": "user", "content": "what time is it"}
    assert msgs[1] == {"role": "assistant", "content": "it's 3pm"}


def test_build_env_context():
    ctx = ContextManager.build_env_context()
    assert "OS:" in ctx
    assert "User:" in ctx
    assert "Python:" in ctx
    assert "Hostname:" in ctx


@pytest.mark.asyncio
async def test_orchestrator_init():
    config = load_config()
    from core.orchestrator import Orchestrator

    mock_llm = MagicMock()
    mock_llm.health = AsyncMock(return_value={"status": "ok"})
    mock_executor = MagicMock()

    orch = Orchestrator(
        config=config,
        llm_client=mock_llm,
        executor=mock_executor,
    )
    assert orch.session_id
    assert isinstance(orch.skills, list)
    assert isinstance(orch.tools, list)
    assert len(orch.skills) >= 7
    assert len(orch.tools) >= 11


@pytest.mark.asyncio
async def test_orchestrator_process_simple():
    """Test orchestrator process with mocked LLM (no tool calls)."""
    config = load_config()
    from core.orchestrator import Orchestrator

    mock_llm = MagicMock()
    # Skill selection returns "none"
    mock_llm.chat_simple = AsyncMock(return_value="none")
    # Main LLM call returns text with no tool calls
    mock_llm.chat = AsyncMock(return_value={"content": "Hello!", "tool_calls": None, "raw": None})
    mock_executor = MagicMock()

    orch = Orchestrator(config=config, llm_client=mock_llm, executor=mock_executor)
    response = await orch.process("hi there")

    assert response.text == "Hello!"
    assert response.tool_calls_made == []
    assert "llm_total" in response.latency_ms
    assert "skill_select" in response.latency_ms
    # Context should have the exchange
    msgs = orch.context.get_messages()
    assert len(msgs) == 2
    assert msgs[0]["content"] == "hi there"
    assert msgs[1]["content"] == "Hello!"

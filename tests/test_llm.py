import pytest

from core.config import load_config
from llm.client import LLMClient
from llm.prompts import build_env_context, build_system_prompt
from llm.tools import get_tools


def test_get_tools_returns_list():
    config = load_config()
    tools = get_tools(config)
    assert isinstance(tools, list)
    assert len(tools) >= 11
    for t in tools:
        assert t["type"] == "function"
        assert "name" in t["function"]


def test_get_tools_excludes_ha_when_disabled():
    config = load_config()
    config.home_assistant.enabled = False
    tools = get_tools(config)
    tool_names = [t["function"]["name"] for t in tools]
    assert "ha_get_states" not in tool_names
    assert "ha_call_service" not in tool_names


def test_get_tools_includes_ha_when_enabled():
    config = load_config()
    config.home_assistant.enabled = True
    tools = get_tools(config)
    tool_names = [t["function"]["name"] for t in tools]
    assert "ha_get_states" in tool_names
    assert "ha_call_service" in tool_names
    assert "ha_get_history" in tool_names


def test_tool_schemas_valid():
    config = load_config()
    tools = get_tools(config)
    for t in tools:
        func = t["function"]
        assert "name" in func
        assert "description" in func
        assert "parameters" in func
        params = func["parameters"]
        assert params["type"] == "object"
        assert "properties" in params


def test_build_system_prompt_base():
    prompt = build_system_prompt()
    assert "VoxaOS" in prompt
    assert "Be concise" in prompt


def test_build_system_prompt_with_skill():
    prompt = build_system_prompt(skill_body="Do a thing")
    assert "Do a thing" in prompt
    assert "Active Skill Instructions" in prompt


def test_build_system_prompt_with_memory():
    prompt = build_system_prompt(memory_context="User likes Rust")
    assert "User likes Rust" in prompt
    assert "Relevant Memories" in prompt


def test_build_system_prompt_with_env():
    prompt = build_system_prompt(env_context="- OS: Linux")
    assert "- OS: Linux" in prompt
    assert "Current Environment" in prompt


def test_build_env_context():
    ctx = build_env_context()
    assert "OS:" in ctx
    assert "Python:" in ctx
    assert "Hostname:" in ctx
    assert "User:" in ctx


@pytest.mark.asyncio
async def test_llm_client_init():
    config = load_config()
    client = LLMClient(config.llm)
    assert client.model == config.llm.api.model
    assert client.config.backend == "api"


@pytest.mark.asyncio
async def test_llm_client_local_init():
    config = load_config()
    config.llm.backend = "local"
    client = LLMClient(config.llm)
    assert client.model == config.llm.local.model

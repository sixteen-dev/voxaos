# Task 02: LLM Client with Tool Calling

## Priority: 2
## Depends on: Task 01 (project skeleton + config)
## Estimated time: 45-60 min

## Objective

Build the async LLM client that talks to Mistral API (default) or local vLLM. Must support tool/function calling. Uses the `openai` Python SDK since both Mistral API and vLLM are OpenAI-compatible.

## What to create

### 1. `llm/client.py`

Async LLM client with factory pattern for API vs local backend.

```python
import os
from openai import AsyncOpenAI
from core.config import LLMConfig
from core.types import ToolCall

class LLMClient:
    def __init__(self, config: LLMConfig):
        self.config = config
        if config.backend == "api":
            api_key = os.environ.get(config.api.api_key_env, "")
            self.client = AsyncOpenAI(
                base_url=config.api.base_url,
                api_key=api_key,
            )
            self.model = config.api.model
        else:
            self.client = AsyncOpenAI(
                base_url=config.local.base_url,
                api_key="not-needed",  # vLLM doesn't need a key
            )
            self.model = config.local.model

    async def chat(self, messages: list[dict], tools: list[dict] | None = None) -> dict:
        """Send messages to LLM, optionally with tool definitions.

        Returns dict with:
          - content: str | None (text response)
          - tool_calls: list[ToolCall] | None (if LLM wants to call tools)
          - raw: the full API response object
        """
        kwargs = {
            "model": self.model,
            "messages": messages,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        response = await self.client.chat.completions.create(**kwargs)
        choice = response.choices[0]

        result = {
            "content": choice.message.content,
            "tool_calls": None,
            "raw": response,
        }

        if choice.message.tool_calls:
            result["tool_calls"] = [
                ToolCall(
                    id=tc.id,
                    name=tc.function.name,
                    args=json.loads(tc.function.arguments),
                )
                for tc in choice.message.tool_calls
            ]

        return result

    async def chat_simple(self, messages: list[dict]) -> str:
        """Simple chat without tools — returns just the text content."""
        result = await self.chat(messages)
        return result["content"] or ""

    async def health(self) -> dict:
        """Check if LLM endpoint is reachable."""
        try:
            models = await self.client.models.list()
            return {"status": "ok", "model": self.model, "backend": self.config.backend}
        except Exception as e:
            return {"status": "error", "error": str(e)}
```

### 2. `llm/tools.py`

All tool definitions in OpenAI function calling format. These get passed to every LLM call that might need tools.

Define these tools:
- `run_shell` — execute shell command
- `read_file` — read file contents
- `write_file` — write/create file
- `list_directory` — list files in a directory
- `search_files` — glob search for files
- `list_processes` — list running processes
- `kill_process` — kill a process by PID
- `launch_app` — launch application
- `open_url` — open URL in browser
- `web_search` — search the web
- `fetch_page` — fetch and extract text from a URL
- `ha_get_states` — get Home Assistant entity states (gated by config)
- `ha_get_state` — get single HA entity state
- `ha_set_state` — update HA entity state
- `ha_call_service` — call HA service to control device
- `ha_get_history` — get HA sensor history

Each tool follows this format:
```python
{
    "type": "function",
    "function": {
        "name": "run_shell",
        "description": "Execute a shell command on the host system. Returns stdout and stderr.",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The shell command to execute"
                }
            },
            "required": ["command"]
        }
    }
}
```

Create a function `get_tools(config) -> list[dict]` that returns all tool definitions. If `config.home_assistant.enabled` is False, exclude the HA tools.

### 3. `llm/prompts.py`

System prompt builder.

```python
import platform
import os

SYSTEM_PROMPT = """You are VoxaOS, a voice-controlled operating system running on an NVIDIA L40S GPU.
You have direct access to the host Linux system through your tools.

Capabilities:
- Execute any shell command
- Read, write, search, and manage files
- Launch applications and manage processes
- Search the web and summarize pages

Rules:
- Be concise. The user is LISTENING to your response, not reading it. Keep answers under 3 sentences unless they ask for detail.
- Use tools proactively. If the user asks "what files are here", use list_directory. Don't guess.
- For destructive operations (delete, kill, overwrite), state what you're about to do and wait for confirmation.
- When reporting tool output, summarize it naturally. Don't read raw JSON or full file contents aloud.
- If a command fails, explain the error briefly and suggest a fix."""

def build_system_prompt(
    env_context: str = "",
    memory_context: str = "",
    skill_body: str = "",
) -> str:
    """Build the full system prompt with dynamic sections."""
    parts = [SYSTEM_PROMPT]

    if env_context:
        parts.append(f"\n\n## Current Environment\n{env_context}")

    if memory_context:
        parts.append(f"\n\n## Relevant Memories\n{memory_context}")

    if skill_body:
        parts.append(f"\n\n## Active Skill Instructions\n{skill_body}")

    return "\n".join(parts)

def build_env_context() -> str:
    """Gather current environment info."""
    return f"""- OS: {platform.system()} {platform.release()}
- Hostname: {platform.node()}
- Working directory: {os.getcwd()}
- User: {os.environ.get('USER', 'unknown')}
- Python: {platform.python_version()}"""
```

## Verification

```python
import asyncio
from core.config import load_config
from llm.client import LLMClient
from llm.tools import get_tools

async def test():
    config = load_config()
    client = LLMClient(config.llm)
    tools = get_tools(config)

    # Test 1: Simple chat
    result = await client.chat_simple([{"role": "user", "content": "Say hello in one word"}])
    print(f"Simple: {result}")

    # Test 2: Tool calling
    result = await client.chat(
        [{"role": "user", "content": "List files in /tmp"}],
        tools=tools,
    )
    print(f"Tool calls: {result['tool_calls']}")

    # Test 3: Health
    health = await client.health()
    print(f"Health: {health}")

asyncio.run(test())
```

Needs `MISTRAL_API_KEY` env var set for API mode.

## Quality Gate

### Test file: `tests/test_llm.py`

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from llm.client import LLMClient
from llm.tools import get_tools
from llm.prompts import build_system_prompt, build_env_context
from core.config import load_config

def test_get_tools_returns_list():
    config = load_config()
    tools = get_tools(config)
    assert isinstance(tools, list)
    assert len(tools) >= 11  # at least the core tools
    for t in tools:
        assert t["type"] == "function"
        assert "name" in t["function"]

def test_get_tools_excludes_ha_when_disabled():
    config = load_config()
    config.home_assistant.enabled = False
    tools = get_tools(config)
    tool_names = [t["function"]["name"] for t in tools]
    assert "ha_get_states" not in tool_names

def test_build_system_prompt_base():
    prompt = build_system_prompt()
    assert "VoxaOS" in prompt

def test_build_system_prompt_with_skill():
    prompt = build_system_prompt(skill_body="Do a thing")
    assert "Do a thing" in prompt

def test_build_env_context():
    ctx = build_env_context()
    assert "OS:" in ctx
    assert "Python:" in ctx

@pytest.mark.asyncio
async def test_llm_client_init():
    config = load_config()
    client = LLMClient(config.llm)
    assert client.model == config.llm.api.model
```

### Run

```bash
ruff check llm/ tests/test_llm.py
mypy llm/client.py llm/tools.py llm/prompts.py
pytest tests/test_llm.py -v
```

| Check | Command | Pass? |
|-------|---------|-------|
| Lint clean | `ruff check llm/ tests/test_llm.py` | |
| Types pass | `mypy llm/client.py llm/tools.py llm/prompts.py` | |
| Tool schema tests | `pytest tests/test_llm.py -v` | |
| Tool count ≥ 11 | Verified in test | |

## Design reference

See PLAN.md sections: "Orchestrator Pattern", "Declarative Tool Definitions", "System Prompt (LLM)", "Home Assistant Integration" (LLM Tool Schemas)

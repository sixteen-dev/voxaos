# Task 06: Orchestrator (The Brain)

## Priority: 6
## Depends on: Task 02 (LLM client), Task 03 (tool executor), Task 04 (skills), Task 05 (memory)
## Estimated time: 60-90 min

## Objective

Build the central orchestrator that ties everything together: context building → skill selection → LLM call → tool call loop → response. This is the brain of VoxaOS. After this task, you can feed text in and get text + tool executions out — no voice needed yet.

## What to create

### 1. `core/context.py`

Manages conversation history and builds environment context.

```python
import os
import platform
from dataclasses import dataclass, field

@dataclass
class ConversationTurn:
    role: str  # "user" or "assistant"
    content: str

class ContextManager:
    def __init__(self, max_history: int = 20):
        self.max_history = max_history
        self.history: list[ConversationTurn] = []

    def add_turn(self, role: str, content: str):
        """Add a conversation turn, trim if exceeding max."""
        self.history.append(ConversationTurn(role=role, content=content))
        if len(self.history) > self.max_history * 2:  # user+assistant pairs
            self.history = self.history[-(self.max_history * 2):]

    def get_messages(self) -> list[dict]:
        """Get conversation history as OpenAI message format."""
        return [{"role": t.role, "content": t.content} for t in self.history]

    def clear(self):
        self.history.clear()

    @staticmethod
    def build_env_context() -> str:
        """Gather current environment info for system prompt."""
        lines = [
            f"- OS: {platform.system()} {platform.release()}",
            f"- Hostname: {platform.node()}",
            f"- Working directory: {os.getcwd()}",
            f"- User: {os.environ.get('USER', 'unknown')}",
            f"- Python: {platform.python_version()}",
        ]
        # GPU info if available
        try:
            import subprocess
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,memory.used,memory.total", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                lines.append(f"- GPU: {result.stdout.strip()}")
        except (FileNotFoundError, subprocess.TimeoutExpired):
            lines.append("- GPU: not available")
        return "\n".join(lines)
```

### 2. `core/orchestrator.py`

The main brain. This is the most critical file in the project.

**Flow:**
```
user_input
    │
    ▼
1. Search memory for relevant context
2. Select skill (lightweight LLM call)
3. Build system prompt (base + env + memory + skill body)
4. Build messages (system + history + user input)
5. Call LLM with tools
6. Tool call loop:
   while LLM returns tool_calls (max N iterations):
     - Execute each tool call via executor
     - Append tool results to messages
     - Call LLM again
7. Get final text response
8. Save to memory (learning + capture)
9. Return Response
```

```python
import time
import uuid
import json
from datetime import datetime
from core.config import Config
from core.types import Response, ToolCall, ToolResult, StreamChunk, StreamChunkType
from core.context import ContextManager
from llm.client import LLMClient
from llm.prompts import build_system_prompt, build_env_context
from llm.tools import get_tools
from tools.executor import ToolExecutor
from skills.loader import Skill, load_skills
from skills.selector import select_skill
from memory.learning import LearningMemory
from memory.capture import CaptureLog
from memory.types import InteractionRecord

class Orchestrator:
    def __init__(
        self,
        config: Config,
        llm_client: LLMClient,
        executor: ToolExecutor,
        learning_memory: LearningMemory | None = None,
        capture_log: CaptureLog | None = None,
    ):
        self.config = config
        self.llm = llm_client
        self.executor = executor
        self.learning_memory = learning_memory
        self.capture_log = capture_log
        self.context = ContextManager(max_history=config.context.max_history)
        self.skills = load_skills("skills")
        self.tools = get_tools(config)
        self.session_id = str(uuid.uuid4())[:8]
        self.pending_briefing: str | None = None

    async def process(self, user_input: str) -> Response:
        """Process a user input through the full pipeline.

        Returns a Response with text, tool calls made, and latency info.
        """
        timing = {}
        tool_calls_made = []
        selected_skill = None

        # --- Step 1: Memory recall ---
        t0 = time.time()
        memory_context = ""
        if self.learning_memory:
            memories = self.learning_memory.search(user_input)
            if memories:
                memory_context = "Relevant memories from past interactions:\n"
                memory_context += "\n".join(f"- {m}" for m in memories)
        timing["memory_search"] = (time.time() - t0) * 1000

        # --- Step 2: Skill selection ---
        t0 = time.time()
        selected_skill = await select_skill(user_input, self.skills, self.llm)
        skill_body = selected_skill.body if selected_skill else ""
        timing["skill_select"] = (time.time() - t0) * 1000

        # --- Step 3: Build system prompt ---
        env_context = ContextManager.build_env_context()
        system_prompt = build_system_prompt(
            env_context=env_context,
            memory_context=memory_context,
            skill_body=skill_body,
        )

        # --- Step 4: Build messages ---
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(self.context.get_messages())
        messages.append({"role": "user", "content": user_input})

        # --- Step 5: LLM call + tool loop ---
        t0 = time.time()
        max_iterations = self.config.llm.max_tool_iterations
        iteration = 0

        while iteration < max_iterations:
            result = await self.llm.chat(messages, tools=self.tools)
            iteration += 1

            if not result["tool_calls"]:
                # LLM gave a final text response — we're done
                break

            # Execute each tool call
            for tc in result["tool_calls"]:
                tool_calls_made.append(tc)
                tool_result = await self.executor.execute(tc)

                # Append tool call + result to messages for next LLM round
                messages.append({
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [{
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.args),
                        }
                    }]
                })
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": tool_result.content,
                })

        timing["llm_total"] = (time.time() - t0) * 1000

        final_text = result["content"] or ""

        # --- Step 6: Update context ---
        self.context.add_turn("user", user_input)
        self.context.add_turn("assistant", final_text)

        # --- Step 7: Save to memory ---
        if self.learning_memory and final_text:
            try:
                self.learning_memory.add(user_input, final_text)
            except Exception:
                pass  # Don't let memory failures break the pipeline

        if self.capture_log:
            try:
                self.capture_log.log(InteractionRecord(
                    session_id=self.session_id,
                    timestamp=datetime.now(),
                    user_transcript=user_input,
                    llm_messages=messages,
                    tool_calls=[{"name": tc.name, "args": tc.args} for tc in tool_calls_made],
                    assistant_response=final_text,
                    skill_used=selected_skill.name if selected_skill else None,
                    latency_ms=timing,
                ))
            except Exception:
                pass

        return Response(
            text=final_text,
            tool_calls_made=tool_calls_made,
            latency_ms=timing,
        )
```

### 3. Wire it all up in `main.py`

Update `main.py` to create and run the orchestrator in a simple REPL loop (for testing without voice/server):

```python
import asyncio
from core.config import load_config
from core.orchestrator import Orchestrator
from llm.client import LLMClient
from tools.executor import ToolExecutor
from tools import register_all_tools
from memory import create_memory

async def main():
    config = load_config()
    print(f"VoxaOS starting in {config.mode.backend} mode")

    # Initialize components
    llm_client = LLMClient(config.llm)
    executor = ToolExecutor(config.tools)
    register_all_tools(executor, config)
    learning_memory, capture_log = create_memory(config)

    orchestrator = Orchestrator(
        config=config,
        llm_client=llm_client,
        executor=executor,
        learning_memory=learning_memory,
        capture_log=capture_log,
    )

    # Health check
    health = await llm_client.health()
    print(f"LLM: {health}")
    print(f"Skills loaded: {len(orchestrator.skills)}")
    print(f"Tools available: {len(orchestrator.tools)}")
    print()

    # Simple text REPL for testing
    print("VoxaOS Text Mode (type 'quit' to exit)")
    print("-" * 40)
    while True:
        user_input = input("\nYou: ").strip()
        if user_input.lower() in ("quit", "exit", "q"):
            break
        if not user_input:
            continue

        response = await orchestrator.process(user_input)
        print(f"\nVoxaOS: {response.text}")
        if response.tool_calls_made:
            print(f"  [Tools used: {', '.join(tc.name for tc in response.tool_calls_made)}]")
        print(f"  [Latency: {response.latency_ms}]")

if __name__ == "__main__":
    asyncio.run(main())
```

## Verification

```bash
# Set API key
export MISTRAL_API_KEY="your-key-here"

# Run the REPL
uv run python main.py

# Test these inputs:
# > List files in /tmp
#   → Should use list_directory tool, return natural language summary
#
# > What time is it?
#   → Should use run_shell with 'date', return time
#
# > Debug why the system feels slow
#   → Should select system-debug skill, run top/free/nvidia-smi
#
# > Search the web for latest Python release
#   → Should select web-research skill or use web_search tool directly
#
# > Create a file called test.py with a hello world program
#   → Should use write_file tool
#
# > What do you remember about me?
#   → Should query learning memory
```

## Quality Gate

### Test file: `tests/test_orchestrator.py`

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from core.context import ContextManager, ConversationTurn
from core.config import load_config

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

def test_build_env_context():
    ctx = ContextManager.build_env_context()
    assert "OS:" in ctx
    assert "User:" in ctx
    assert "Python:" in ctx

@pytest.mark.asyncio
async def test_orchestrator_init():
    """Orchestrator initializes with all components."""
    config = load_config()
    # Use mocks to avoid needing real API keys
    from core.orchestrator import Orchestrator
    mock_llm = MagicMock()
    mock_llm.health = AsyncMock(return_value={"status": "ok"})
    mock_executor = MagicMock()

    orch = Orchestrator(
        config=config, llm_client=mock_llm, executor=mock_executor,
    )
    assert orch.session_id
    assert isinstance(orch.skills, list)
    assert isinstance(orch.tools, list)
```

### Run

```bash
uv run ruff check core/context.py core/orchestrator.py tests/test_orchestrator.py
uv run mypy core/context.py
uv run pytest tests/test_orchestrator.py -v
```

| Check | Command | Pass? |
|-------|---------|-------|
| Lint clean | `uv run ruff check core/ tests/test_orchestrator.py` | |
| Types pass | `uv run mypy core/context.py` | |
| Context manager | `uv run pytest tests/test_orchestrator.py -k context -v` | |
| Orchestrator init | `uv run pytest tests/test_orchestrator.py::test_orchestrator_init` | |
| Text REPL starts | `python main.py` starts without crash (manual) | |

## Design reference

See PLAN.md sections: "Orchestrator Pattern", "Two-stage skill selection + execution flow", "Context Manager with Conversation History"

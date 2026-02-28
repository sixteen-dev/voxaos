import json
import time
import uuid
from datetime import datetime

from core.config import Config
from core.context import ContextManager
from core.types import Response, ToolCall
from llm.client import LLMClient
from llm.prompts import build_system_prompt
from llm.tools import get_tools
from memory.capture import CaptureLog
from memory.learning import LearningMemory
from memory.types import InteractionRecord
from skills.loader import load_skills
from skills.selector import select_skill
from tools.executor import ToolExecutor


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

    async def process(self, user_input: str) -> Response:
        """Process user input through the full pipeline.

        Returns a Response with text, tool calls made, and latency info.
        """
        timing: dict[str, float] = {}
        tool_calls_made: list[ToolCall] = []
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
        messages: list[dict] = [{"role": "system", "content": system_prompt}]
        messages.extend(self.context.get_messages())
        messages.append({"role": "user", "content": user_input})

        # --- Step 5: LLM call + tool loop ---
        t0 = time.time()
        max_iterations = self.config.llm.max_tool_iterations
        result: dict = {}

        for _ in range(max_iterations):
            result = await self.llm.chat(messages, tools=self.tools)

            if not result["tool_calls"]:
                break

            # Execute each tool call
            for tc in result["tool_calls"]:
                tool_calls_made.append(tc)
                tool_result = await self.executor.execute(tc)

                messages.append(
                    {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": tc.id,
                                "type": "function",
                                "function": {
                                    "name": tc.name,
                                    "arguments": json.dumps(tc.args),
                                },
                            }
                        ],
                    }
                )
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": tool_result.content,
                    }
                )

        timing["llm_total"] = (time.time() - t0) * 1000

        final_text = result.get("content") or ""

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
                self.capture_log.log(
                    InteractionRecord(
                        session_id=self.session_id,
                        timestamp=datetime.now(),
                        user_transcript=user_input,
                        llm_messages=messages,
                        tool_calls=[{"name": tc.name, "args": tc.args} for tc in tool_calls_made],
                        assistant_response=final_text,
                        skill_used=selected_skill.name if selected_skill else None,
                        latency_ms=timing,
                    )
                )
            except Exception:
                pass

        return Response(
            text=final_text,
            tool_calls_made=tool_calls_made,
            latency_ms=timing,
        )

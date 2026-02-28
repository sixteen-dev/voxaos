import json
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
                api_key="not-needed",
            )
            self.model = config.local.model

    async def chat(self, messages: list[dict], tools: list[dict] | None = None) -> dict:
        """Send messages to LLM, optionally with tool definitions.

        Returns dict with:
          - content: str | None (text response)
          - tool_calls: list[ToolCall] | None (if LLM wants to call tools)
          - raw: the full API response object
        """
        kwargs: dict = {
            "model": self.model,
            "messages": messages,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        response = await self.client.chat.completions.create(**kwargs)
        choice = response.choices[0]

        result: dict = {
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
            await self.client.models.list()
            return {"status": "ok", "model": self.model, "backend": self.config.backend}
        except Exception as e:
            return {"status": "error", "error": str(e)}

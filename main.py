import asyncio
import sys

import uvicorn

from core.config import load_config
from core.orchestrator import Orchestrator
from llm.client import LLMClient
from memory import create_memory
from tools import register_all_tools
from tools.executor import ToolExecutor


async def text_repl() -> None:
    """Text-only REPL for testing orchestrator without voice."""
    config = load_config()
    print(f"VoxaOS starting in {config.mode.backend} mode")

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

    health = await llm_client.health()
    print(f"LLM: {health}")
    print(f"Skills loaded: {len(orchestrator.skills)}")
    print(f"Tools available: {len(orchestrator.tools)}")
    print()

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


def server() -> None:
    """Start FastAPI server with voice pipeline."""
    config = load_config()
    print(f"VoxaOS starting in {config.mode.backend} mode")
    print(f"Server: http://{config.server.host}:{config.server.port}")
    uvicorn.run(
        "server.app:app",
        host=config.server.host,
        port=config.server.port,
        reload=False,
    )


if __name__ == "__main__":
    if "--text" in sys.argv:
        asyncio.run(text_repl())
    else:
        server()

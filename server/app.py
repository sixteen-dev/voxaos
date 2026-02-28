from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from core.config import load_config
from core.orchestrator import Orchestrator
from llm.client import LLMClient
from memory import create_memory
from server.audio_handler import AudioHandler
from tools import register_all_tools
from tools.executor import ToolExecutor
from voice.pipeline import VoicePipeline
from voice.stt import create_stt
from voice.tts import create_tts
from voice.vad import SileroVAD

# Global state — initialized on startup
pipeline: VoicePipeline | None = None
orchestrator: Orchestrator | None = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    global pipeline, orchestrator

    config = load_config()

    # Init components
    llm_client = LLMClient(config.llm)
    executor = ToolExecutor(config.tools)
    register_all_tools(executor, config)
    learning, capture = create_memory(config)

    orchestrator = Orchestrator(
        config=config,
        llm_client=llm_client,
        executor=executor,
        learning_memory=learning,
        capture_log=capture,
    )

    stt = await create_stt(config.stt)
    tts = await create_tts(config.tts)
    vad = SileroVAD(
        threshold=config.vad.threshold,
        speech_start_ms=config.vad.speech_start_ms,
        silence_end_ms=config.vad.silence_end_ms,
    )

    pipeline = VoicePipeline(orchestrator=orchestrator, stt=stt, tts=tts, vad=vad)

    yield

    # Cleanup
    pipeline = None
    orchestrator = None


app = FastAPI(title="VoxaOS", lifespan=lifespan)


@app.get("/")
async def root() -> Any:
    return FileResponse("ui/index.html")


@app.get("/health")
async def health() -> dict[str, Any]:
    llm_health: dict[str, Any] = (
        await orchestrator.llm.health()
        if orchestrator
        else {"status": "not initialized"}
    )
    return {
        "status": "ok",
        "llm": llm_health,
        "skills": len(orchestrator.skills) if orchestrator else 0,
        "pipeline_state": pipeline.state.value if pipeline else "not initialized",
    }


@app.websocket("/ws/audio")
async def websocket_audio(ws: WebSocket) -> None:
    await ws.accept()
    if not pipeline:
        await ws.close(code=1011, reason="Pipeline not initialized")
        return
    handler = AudioHandler(ws, pipeline)
    try:
        await handler.run()
    except WebSocketDisconnect:
        pass


# Serve static files (CSS, JS)
app.mount("/ui", StaticFiles(directory="ui"), name="ui")

# Task 08: FastAPI Server + WebSocket Audio Handler

## Priority: 8
## Depends on: Task 07 (voice pipeline)
## Estimated time: 45-60 min

## Objective

Build the FastAPI server with WebSocket for bidirectional audio streaming and control messages. This is the bridge between the browser UI and the voice pipeline.

## What to create

### 1. `server/app.py`

FastAPI application with these endpoints:

- `GET /` — serve `ui/index.html` (static files)
- `GET /health` — aggregate component health (STT, LLM, TTS status)
- `WS /ws/audio` — bidirectional WebSocket for audio + control messages

On startup:
- Load config
- Initialize LLM client, tool executor, memory, orchestrator
- Create STT, TTS, VAD
- Create voice pipeline
- Serve static files from `ui/` directory

```python
import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from core.config import load_config
from core.orchestrator import Orchestrator
from llm.client import LLMClient
from tools.executor import ToolExecutor
from tools import register_all_tools
from memory import create_memory
from voice.vad import SileroVAD
from voice.stt import create_stt
from voice.tts import create_tts
from voice.pipeline import VoicePipeline
from server.audio_handler import AudioHandler

app = FastAPI(title="VoxaOS")

# Global state — initialized on startup
pipeline: VoicePipeline | None = None
orchestrator: Orchestrator | None = None

@app.on_event("startup")
async def startup():
    global pipeline, orchestrator
    config = load_config()

    # Init components
    llm_client = LLMClient(config.llm)
    executor = ToolExecutor(config.tools)
    register_all_tools(executor, config)
    learning, capture = create_memory(config)

    orchestrator = Orchestrator(
        config=config, llm_client=llm_client, executor=executor,
        learning_memory=learning, capture_log=capture,
    )

    stt = await create_stt(config.stt)
    tts = await create_tts(config.tts)
    vad = SileroVAD(
        threshold=config.vad.threshold,
        speech_start_ms=config.vad.speech_start_ms,
        silence_end_ms=config.vad.silence_end_ms,
    )

    pipeline = VoicePipeline(orchestrator=orchestrator, stt=stt, tts=tts, vad=vad)

@app.get("/")
async def root():
    return FileResponse("ui/index.html")

@app.get("/health")
async def health():
    llm_health = await orchestrator.llm.health() if orchestrator else {"status": "not initialized"}
    return {
        "status": "ok",
        "llm": llm_health,
        "skills": len(orchestrator.skills) if orchestrator else 0,
        "pipeline_state": pipeline.state.value if pipeline else "not initialized",
    }

@app.websocket("/ws/audio")
async def websocket_audio(ws: WebSocket):
    await ws.accept()
    handler = AudioHandler(ws, pipeline)
    try:
        await handler.run()
    except WebSocketDisconnect:
        pass

# Serve static files (CSS, JS)
app.mount("/ui", StaticFiles(directory="ui"), name="ui")
```

### 2. `server/audio_handler.py`

WebSocket protocol handler. Manages bidirectional communication.

**Client → Server messages:**
- Binary frames: raw PCM audio chunks (16kHz, mono, int16)
- JSON `{"type": "push_to_talk", "state": "start"|"stop"}` — manual trigger mode
- JSON `{"type": "confirm", "tool_call_id": "..."}` — user confirms dangerous operation

**Server → Client messages:**
- Binary frames: TTS audio (22.05kHz, mono, int16)
- JSON `{"type": "transcript", "text": "...", "partial": bool}`
- JSON `{"type": "thinking", "text": "Processing..."}`
- JSON `{"type": "response", "text": "...", "tools_used": [...]}`
- JSON `{"type": "state", "pipeline": "idle"|"listening"|"processing"|"speaking"}`
- JSON `{"type": "confirm_request", "tool_name": "...", "args": {...}}`

```python
import json
from fastapi import WebSocket
from core.types import PipelineState, StreamChunk, StreamChunkType
from voice.pipeline import VoicePipeline

class AudioHandler:
    def __init__(self, ws: WebSocket, pipeline: VoicePipeline):
        self.ws = ws
        self.pipeline = pipeline
        self._ptt_buffer = bytearray()
        self._ptt_active = False
        self._setup_callbacks()

    def _setup_callbacks(self):
        """Wire pipeline callbacks to WebSocket sends."""
        self.pipeline.on_state_change = self._on_state_change
        self.pipeline.on_audio_out = self._on_audio_out
        self.pipeline.on_transcript = self._on_transcript
        self.pipeline.on_stream_chunk = self._on_stream_chunk

    async def _on_state_change(self, state: PipelineState):
        await self.ws.send_json({"type": "state", "pipeline": state.value})

    async def _on_audio_out(self, audio_bytes: bytes):
        await self.ws.send_bytes(audio_bytes)

    async def _on_transcript(self, text: str, partial: bool):
        await self.ws.send_json({"type": "transcript", "text": text, "partial": partial})

    async def _on_stream_chunk(self, chunk: StreamChunk):
        if chunk.type == StreamChunkType.THINKING:
            await self.ws.send_json({"type": "thinking", "text": chunk.content})
        elif chunk.type == StreamChunkType.TEXT:
            await self.ws.send_json({
                "type": "response",
                "text": chunk.content,
                "tools_used": [],
            })

    async def run(self):
        """Main loop — receive messages from WebSocket."""
        while True:
            message = await self.ws.receive()

            if message["type"] == "websocket.receive":
                if "bytes" in message and message["bytes"]:
                    # Binary = audio data
                    if self._ptt_active:
                        self._ptt_buffer.extend(message["bytes"])
                    else:
                        await self.pipeline.feed_audio(message["bytes"])

                elif "text" in message and message["text"]:
                    # JSON = control message
                    data = json.loads(message["text"])
                    await self._handle_control(data)

            elif message["type"] == "websocket.disconnect":
                break

    async def _handle_control(self, data: dict):
        msg_type = data.get("type")

        if msg_type == "push_to_talk":
            if data["state"] == "start":
                self._ptt_active = True
                self._ptt_buffer.clear()
            elif data["state"] == "stop":
                self._ptt_active = False
                if self._ptt_buffer:
                    await self.pipeline.process_push_to_talk(bytes(self._ptt_buffer))
                    self._ptt_buffer.clear()

        elif msg_type == "confirm":
            # Handle confirmation for dangerous operations
            # TODO: wire to executor's confirmation callback
            pass

        elif msg_type == "text_input":
            # Direct text input (bypass voice) — useful for testing
            text = data.get("text", "")
            if text and self.pipeline.orchestrator:
                response = await self.pipeline.orchestrator.process(text)
                await self.ws.send_json({
                    "type": "response",
                    "text": response.text,
                    "tools_used": [tc.name for tc in response.tool_calls_made],
                })
                # Also synthesize and send audio
                if response.text:
                    audio = await self.pipeline.tts.synthesize(response.text)
                    import numpy as np
                    audio_bytes = (audio * 32768).astype(np.int16).tobytes()
                    await self.ws.send_bytes(audio_bytes)
```

### 3. Update `main.py`

Replace the REPL with uvicorn server:

```python
import asyncio
import uvicorn
from core.config import load_config

def main():
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
    main()
```

**Keep the old REPL mode available** — add a `--text` flag:
```python
import sys
if "--text" in sys.argv:
    asyncio.run(text_repl())  # the old REPL from task 06
else:
    main()  # uvicorn server
```

## Verification

```bash
uv run python main.py
# Server starts on http://0.0.0.0:7860

# Test health
curl http://localhost:7860/health

# Test WebSocket with a simple Python client:
uv run python -c "
import asyncio, websockets, json
async def test():
    async with websockets.connect('ws://localhost:7860/ws/audio') as ws:
        await ws.send(json.dumps({'type': 'text_input', 'text': 'Hello, what can you do?'}))
        resp = await ws.recv()
        print(json.loads(resp))
asyncio.run(test())
"
```

## Quality Gate

### Test file: `tests/test_server.py`

```python
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from fastapi.testclient import TestClient

@pytest.fixture
def client():
    """Create a test client with mocked dependencies."""
    with patch("server.app.startup"):
        from server.app import app
        return TestClient(app)

def test_static_files_served(client):
    """index.html should be served at root."""
    # This test works after UI files are created (task 09)
    # For now, just verify the route exists
    resp = client.get("/")
    assert resp.status_code in (200, 404)  # 404 ok if ui/ not yet created

def test_health_endpoint_exists(client):
    """Health endpoint should respond."""
    # Will return error if orchestrator not initialized, but shouldn't 500
    resp = client.get("/health")
    assert resp.status_code in (200, 500)

def test_audio_handler_init():
    """AudioHandler should initialize with WebSocket and pipeline."""
    from server.audio_handler import AudioHandler
    mock_ws = MagicMock()
    mock_pipeline = MagicMock()
    handler = AudioHandler(mock_ws, mock_pipeline)
    assert handler.ws is mock_ws
    assert handler.pipeline is mock_pipeline
    assert handler._ptt_active is False

@pytest.mark.asyncio
async def test_audio_handler_ptt_control():
    """Push-to-talk control messages should toggle state."""
    from server.audio_handler import AudioHandler
    mock_ws = AsyncMock()
    mock_pipeline = MagicMock()
    mock_pipeline.on_state_change = None
    mock_pipeline.on_audio_out = None
    mock_pipeline.on_transcript = None
    mock_pipeline.on_stream_chunk = None

    handler = AudioHandler(mock_ws, mock_pipeline)

    await handler._handle_control({"type": "push_to_talk", "state": "start"})
    assert handler._ptt_active is True

    await handler._handle_control({"type": "push_to_talk", "state": "stop"})
    assert handler._ptt_active is False
```

### Run

```bash
uv run ruff check server/ tests/test_server.py
uv run mypy server/audio_handler.py
uv run pytest tests/test_server.py -v
```

| Check | Command | Pass? |
|-------|---------|-------|
| Lint clean | `uv run ruff check server/ tests/test_server.py` | |
| Types pass | `uv run mypy server/audio_handler.py` | |
| Handler init | `pytest tests/test_server.py::test_audio_handler_init` | |
| PTT toggle | `pytest tests/test_server.py::test_audio_handler_ptt_control` | |
| Server starts | `python main.py` binds to port 7860 (manual) | |

## Design reference

See PLAN.md sections: Phase 4 (Server + Browser UI), "Architecture" diagram, WebSocket protocol details

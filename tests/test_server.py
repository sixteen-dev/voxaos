import json
from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pytest

from core.types import PipelineState, Response, StreamChunk, StreamChunkType


def test_audio_handler_init():
    """AudioHandler should initialize with WebSocket and pipeline."""
    from server.audio_handler import AudioHandler

    mock_ws = MagicMock()
    mock_pipeline = MagicMock()
    handler = AudioHandler(mock_ws, mock_pipeline)
    assert handler.ws is mock_ws
    assert handler.pipeline is mock_pipeline
    assert handler._ptt_active is False
    assert handler._ptt_buffer == bytearray()


def test_audio_handler_sets_callbacks():
    """AudioHandler should wire pipeline callbacks on init."""
    from server.audio_handler import AudioHandler

    mock_ws = MagicMock()
    mock_pipeline = MagicMock()
    AudioHandler(mock_ws, mock_pipeline)
    assert mock_pipeline.on_state_change is not None
    assert mock_pipeline.on_audio_out is not None
    assert mock_pipeline.on_transcript is not None
    assert mock_pipeline.on_stream_chunk is not None


@pytest.mark.asyncio
async def test_audio_handler_ptt_start():
    """Push-to-talk start should toggle state."""
    from server.audio_handler import AudioHandler

    mock_ws = AsyncMock()
    mock_pipeline = MagicMock()
    handler = AudioHandler(mock_ws, mock_pipeline)

    await handler._handle_control({"type": "push_to_talk", "state": "start"})
    assert handler._ptt_active is True


@pytest.mark.asyncio
async def test_audio_handler_ptt_stop_empty():
    """Push-to-talk stop with no audio should just toggle state."""
    from server.audio_handler import AudioHandler

    mock_ws = AsyncMock()
    mock_pipeline = MagicMock()
    mock_pipeline.process_push_to_talk = AsyncMock()
    handler = AudioHandler(mock_ws, mock_pipeline)

    handler._ptt_active = True
    await handler._handle_control({"type": "push_to_talk", "state": "stop"})
    assert handler._ptt_active is False
    mock_pipeline.process_push_to_talk.assert_not_called()


@pytest.mark.asyncio
async def test_audio_handler_ptt_stop_with_audio():
    """Push-to-talk stop with buffered audio should process it."""
    from server.audio_handler import AudioHandler

    mock_ws = AsyncMock()
    mock_pipeline = MagicMock()
    mock_pipeline.process_push_to_talk = AsyncMock()
    handler = AudioHandler(mock_ws, mock_pipeline)

    handler._ptt_active = True
    handler._ptt_buffer = bytearray(b"\x00\x01\x02\x03")
    await handler._handle_control({"type": "push_to_talk", "state": "stop"})
    assert handler._ptt_active is False
    mock_pipeline.process_push_to_talk.assert_called_once()
    assert handler._ptt_buffer == bytearray()


@pytest.mark.asyncio
async def test_audio_handler_state_change_callback():
    """State change callback should send JSON to WebSocket."""
    from server.audio_handler import AudioHandler

    mock_ws = AsyncMock()
    mock_pipeline = MagicMock()
    handler = AudioHandler(mock_ws, mock_pipeline)

    await handler._on_state_change(PipelineState.LISTENING)
    mock_ws.send_json.assert_called_with({"type": "state", "pipeline": "listening"})


@pytest.mark.asyncio
async def test_audio_handler_audio_out_callback():
    """Audio out callback should send binary to WebSocket."""
    from server.audio_handler import AudioHandler

    mock_ws = AsyncMock()
    mock_pipeline = MagicMock()
    handler = AudioHandler(mock_ws, mock_pipeline)

    audio_bytes = b"\x00\x01\x02\x03"
    await handler._on_audio_out(audio_bytes)
    mock_ws.send_bytes.assert_called_with(audio_bytes)


@pytest.mark.asyncio
async def test_audio_handler_transcript_callback():
    """Transcript callback should send JSON to WebSocket."""
    from server.audio_handler import AudioHandler

    mock_ws = AsyncMock()
    mock_pipeline = MagicMock()
    handler = AudioHandler(mock_ws, mock_pipeline)

    await handler._on_transcript("hello world", False)
    mock_ws.send_json.assert_called_with({"type": "transcript", "text": "hello world", "partial": False})


@pytest.mark.asyncio
async def test_audio_handler_stream_chunk_text():
    """Text stream chunk should send response JSON."""
    from server.audio_handler import AudioHandler

    mock_ws = AsyncMock()
    mock_pipeline = MagicMock()
    handler = AudioHandler(mock_ws, mock_pipeline)

    chunk = StreamChunk(type=StreamChunkType.TEXT, content="Here's what I found")
    await handler._on_stream_chunk(chunk)
    mock_ws.send_json.assert_called_with({
        "type": "response",
        "text": "Here's what I found",
        "tools_used": [],
    })


@pytest.mark.asyncio
async def test_audio_handler_stream_chunk_thinking():
    """Thinking stream chunk should send thinking JSON."""
    from server.audio_handler import AudioHandler

    mock_ws = AsyncMock()
    mock_pipeline = MagicMock()
    handler = AudioHandler(mock_ws, mock_pipeline)

    chunk = StreamChunk(type=StreamChunkType.THINKING, content="Processing...")
    await handler._on_stream_chunk(chunk)
    mock_ws.send_json.assert_called_with({"type": "thinking", "text": "Processing..."})


@pytest.mark.asyncio
async def test_audio_handler_text_input():
    """Text input control message should bypass voice and use orchestrator."""
    from server.audio_handler import AudioHandler

    mock_ws = AsyncMock()
    mock_pipeline = MagicMock()
    mock_pipeline.orchestrator = MagicMock()
    mock_pipeline.orchestrator.process = AsyncMock(
        return_value=Response(text="Hello!", tool_calls_made=[], latency_ms={})
    )
    mock_pipeline.tts = MagicMock()
    mock_pipeline.tts.synthesize = AsyncMock(return_value=np.zeros(100, dtype=np.float32))
    handler = AudioHandler(mock_ws, mock_pipeline)

    await handler._handle_control({"type": "text_input", "text": "Hi there"})
    mock_pipeline.orchestrator.process.assert_called_once_with("Hi there")
    # Should send JSON response + binary audio
    assert mock_ws.send_json.called
    assert mock_ws.send_bytes.called


@pytest.mark.asyncio
async def test_audio_handler_run_binary():
    """Run loop should feed binary audio to pipeline."""
    from server.audio_handler import AudioHandler

    mock_ws = AsyncMock()
    mock_pipeline = MagicMock()
    mock_pipeline.feed_audio = AsyncMock()

    audio_chunk = np.zeros(512, dtype=np.int16).tobytes()
    mock_ws.receive = AsyncMock(side_effect=[
        {"type": "websocket.receive", "bytes": audio_chunk, "text": None},
        {"type": "websocket.disconnect"},
    ])
    handler = AudioHandler(mock_ws, mock_pipeline)

    await handler.run()
    mock_pipeline.feed_audio.assert_called_once_with(audio_chunk)


@pytest.mark.asyncio
async def test_audio_handler_run_json():
    """Run loop should dispatch JSON control messages."""
    from server.audio_handler import AudioHandler

    mock_ws = AsyncMock()
    mock_pipeline = MagicMock()

    control_msg = json.dumps({"type": "push_to_talk", "state": "start"})
    mock_ws.receive = AsyncMock(side_effect=[
        {"type": "websocket.receive", "bytes": None, "text": control_msg},
        {"type": "websocket.disconnect"},
    ])
    handler = AudioHandler(mock_ws, mock_pipeline)

    await handler.run()
    assert handler._ptt_active is True


def test_app_routes_exist():
    """App should have root, health, and websocket routes."""
    from server.app import app

    routes = [r.path for r in app.routes]
    assert "/" in routes
    assert "/health" in routes
    assert "/ws/audio" in routes

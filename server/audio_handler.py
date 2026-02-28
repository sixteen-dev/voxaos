import json
from typing import Any

import numpy as np
from fastapi import WebSocket

from core.types import PipelineState, StreamChunk, StreamChunkType
from voice.pipeline import VoicePipeline


class AudioHandler:
    """WebSocket protocol handler for bidirectional audio + control messages."""

    def __init__(self, ws: WebSocket, pipeline: VoicePipeline):
        self.ws = ws
        self.pipeline = pipeline
        self._ptt_buffer = bytearray()
        self._ptt_active = False
        self._setup_callbacks()

    def _setup_callbacks(self) -> None:
        """Wire pipeline callbacks to WebSocket sends."""
        self.pipeline.on_state_change = self._on_state_change
        self.pipeline.on_audio_out = self._on_audio_out
        self.pipeline.on_transcript = self._on_transcript
        self.pipeline.on_stream_chunk = self._on_stream_chunk

    async def _on_state_change(self, state: PipelineState) -> None:
        await self.ws.send_json({"type": "state", "pipeline": state.value})

    async def _on_audio_out(self, audio_bytes: bytes) -> None:
        await self.ws.send_bytes(audio_bytes)

    async def _on_transcript(self, text: str, partial: bool) -> None:
        await self.ws.send_json({"type": "transcript", "text": text, "partial": partial})

    async def _on_stream_chunk(self, chunk: StreamChunk) -> None:
        if chunk.type == StreamChunkType.THINKING:
            await self.ws.send_json({"type": "thinking", "text": chunk.content})
        elif chunk.type == StreamChunkType.TEXT:
            await self.ws.send_json({
                "type": "response",
                "text": chunk.content,
                "tools_used": [],
            })
        elif chunk.type == StreamChunkType.TRANSCRIPT:
            await self.ws.send_json({
                "type": "transcript",
                "text": chunk.content,
                "partial": False,
            })

    async def run(self) -> None:
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
                    data: dict[str, Any] = json.loads(message["text"])
                    await self._handle_control(data)

            elif message["type"] == "websocket.disconnect":
                break

    async def _handle_control(self, data: dict[str, Any]) -> None:
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

        elif msg_type == "text_input":
            # Direct text input (bypass voice) — useful for testing
            text = data.get("text", "")
            if text and self.pipeline.orchestrator:
                try:
                    response = await self.pipeline.orchestrator.process(text)
                except Exception as e:
                    await self.ws.send_json({
                        "type": "response",
                        "text": f"I'm having trouble connecting to my brain. Try again in a moment. ({e})",
                        "tools_used": [],
                    })
                    return

                await self.ws.send_json({
                    "type": "response",
                    "text": response.text,
                    "tools_used": [tc.name for tc in response.tool_calls_made],
                })

                # Send latency info
                if response.latency_ms:
                    latency_str = " | ".join(f"{k}: {v:.0f}ms" for k, v in response.latency_ms.items())
                    await self.ws.send_json({"type": "thinking", "text": latency_str})

                # Synthesize and send audio
                if response.text:
                    try:
                        audio = await self.pipeline.tts.synthesize(response.text)
                        audio_int16 = (audio * 32768).astype(np.int16)
                        await self.ws.send_bytes(audio_int16.tobytes())
                    except Exception:
                        pass  # TTS failure — text response already sent

        elif msg_type == "confirm":
            # Handle confirmation for dangerous operations
            # TODO: wire to executor's confirmation callback
            pass

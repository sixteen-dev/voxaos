from collections.abc import Callable, Coroutine
from typing import Any

import numpy as np

from core.orchestrator import Orchestrator
from core.types import PipelineState, StreamChunk, StreamChunkType
from voice.stt import STTEngine
from voice.tts import TTSEngine
from voice.vad import SileroVAD

# Type alias for async callbacks
AsyncCallback = Callable[..., Coroutine[Any, Any, None]]


class VoicePipeline:
    """State machine: IDLE → LISTENING → PROCESSING → SPEAKING → IDLE."""

    def __init__(
        self,
        orchestrator: Orchestrator,
        stt: STTEngine,
        tts: TTSEngine,
        vad: SileroVAD,
    ):
        self.orchestrator = orchestrator
        self.stt = stt
        self.tts = tts
        self.vad = vad
        self.state = PipelineState.IDLE
        self._audio_buffer: list[np.ndarray] = []

        # Callbacks — set by server/WebSocket handler
        self.on_state_change: AsyncCallback | None = None
        self.on_audio_out: AsyncCallback | None = None
        self.on_transcript: AsyncCallback | None = None
        self.on_stream_chunk: AsyncCallback | None = None

    async def _set_state(self, new_state: PipelineState) -> None:
        self.state = new_state
        if self.on_state_change:
            await self.on_state_change(new_state)
        if self.on_stream_chunk:
            await self.on_stream_chunk(StreamChunk(type=StreamChunkType.STATE, content=new_state.value))

    async def feed_audio(self, chunk: bytes) -> None:
        """Feed raw PCM int16 audio from the client.

        Each chunk should be 480 samples (30ms at 16kHz) = 960 bytes.
        """
        # Ignore audio while speaking (no barge-in for hackathon)
        if self.state == PipelineState.SPEAKING:
            return
        # Ignore audio while processing
        if self.state == PipelineState.PROCESSING:
            return

        # Convert int16 PCM bytes → float32 numpy
        audio_int16 = np.frombuffer(chunk, dtype=np.int16)
        audio_float = audio_int16.astype(np.float32) / 32768.0

        # Run VAD
        vad_result = self.vad.process_chunk(audio_float)

        if vad_result["speech_start"]:
            await self._set_state(PipelineState.LISTENING)
            self._audio_buffer.clear()

        if self.state == PipelineState.LISTENING:
            self._audio_buffer.append(audio_float)

        if vad_result["speech_end"] and self.state == PipelineState.LISTENING:
            await self._process_utterance()

    async def process_push_to_talk(self, audio_data: bytes) -> None:
        """Bypass VAD — process a complete audio chunk directly."""
        audio_int16 = np.frombuffer(audio_data, dtype=np.int16)
        audio_float = audio_int16.astype(np.float32) / 32768.0
        self._audio_buffer = [audio_float]
        await self._process_utterance()

    async def _process_utterance(self) -> None:
        """Full pipeline: STT → Orchestrator → TTS with latency tracking."""
        import time

        timing: dict[str, float] = {}
        await self._set_state(PipelineState.PROCESSING)

        # Concatenate buffered audio
        if not self._audio_buffer:
            await self._set_state(PipelineState.IDLE)
            return

        audio = np.concatenate(self._audio_buffer)
        self._audio_buffer.clear()
        self.vad.reset()

        # --- STT ---
        t0 = time.time()
        try:
            transcript = await self.stt.transcribe(audio)
        except Exception as e:
            transcript = ""
            if self.on_stream_chunk:
                await self.on_stream_chunk(
                    StreamChunk(type=StreamChunkType.TEXT, content=f"I couldn't process the audio: {e}")
                )
        timing["stt"] = (time.time() - t0) * 1000

        if self.on_transcript:
            await self.on_transcript(transcript, False)
        if self.on_stream_chunk:
            await self.on_stream_chunk(StreamChunk(type=StreamChunkType.TRANSCRIPT, content=transcript))

        if not transcript.strip():
            if self.on_stream_chunk:
                await self.on_stream_chunk(
                    StreamChunk(type=StreamChunkType.TEXT, content="I didn't catch that. Could you repeat?")
                )
            await self._set_state(PipelineState.IDLE)
            return

        # --- Orchestrator ---
        t0 = time.time()
        try:
            response = await self.orchestrator.process(transcript)
        except Exception as e:
            if self.on_stream_chunk:
                await self.on_stream_chunk(
                    StreamChunk(
                        type=StreamChunkType.TEXT,
                        content="I'm having trouble connecting to my brain. Try again in a moment.",
                    )
                )
            await self._set_state(PipelineState.IDLE)
            return
        timing["orchestrator"] = (time.time() - t0) * 1000
        timing.update(response.latency_ms)

        if self.on_stream_chunk:
            await self.on_stream_chunk(StreamChunk(type=StreamChunkType.TEXT, content=response.text))

        if not response.text.strip():
            await self._set_state(PipelineState.IDLE)
            return

        # --- TTS ---
        await self._set_state(PipelineState.SPEAKING)

        t0 = time.time()
        try:
            tts_audio = await self.tts.synthesize(response.text)
            # Convert float32 → int16 PCM bytes for client
            audio_int16 = (tts_audio * 32767).astype(np.int16)
            audio_bytes = audio_int16.tobytes()

            if self.on_audio_out:
                await self.on_audio_out(audio_bytes)
            if self.on_stream_chunk:
                await self.on_stream_chunk(StreamChunk(type=StreamChunkType.AUDIO, content=audio_bytes))
        except Exception as e:
            # TTS failed — still return text response (just no audio)
            if self.on_stream_chunk:
                await self.on_stream_chunk(
                    StreamChunk(type=StreamChunkType.TEXT, content=f"(Voice unavailable: {e})")
                )
        timing["tts"] = (time.time() - t0) * 1000
        timing["total"] = sum(timing.values())

        # Send latency info to client
        if self.on_stream_chunk:
            latency_str = " | ".join(f"{k}: {v:.0f}ms" for k, v in timing.items())
            await self.on_stream_chunk(StreamChunk(type=StreamChunkType.THINKING, content=latency_str))

        await self._set_state(PipelineState.IDLE)

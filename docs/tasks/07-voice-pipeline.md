# Task 07: Voice Pipeline (VAD + STT + TTS + State Machine)

## Priority: 7
## Depends on: Task 06 (orchestrator)
## Estimated time: 60-90 min

## Objective

Build the voice pipeline: audio in → VAD → STT → orchestrator → TTS → audio out. Uses API backends by default (Mistral API for STT, NVIDIA Riva API for TTS). Includes Silero VAD for speech detection and a state machine managing the pipeline flow.

## What to create

### 1. `voice/vad.py`

Silero VAD wrapper. Runs on CPU, ~2MB model. Detects when someone starts/stops speaking.

Key design:
- Load Silero VAD via `torch.hub.load('snakers4/silero-vad', 'silero_vad')`
- `process_chunk(audio_chunk: np.ndarray) -> dict` returns `{is_speech, speech_start, speech_end, speech_prob}`
- Tracks consecutive speech/silence frames to determine speech start (300ms) and end (500ms)
- `reset()` clears state between utterances
- Each chunk is 30ms at 16kHz = 480 samples

### 2. `voice/stt.py`

STT with factory pattern. Abstract base class `STTEngine` with `async def transcribe(audio, sample_rate) -> str`.

**API mode (`MistralSTTAPI`):**
- Send audio as WAV bytes to Mistral Voxtral API
- Convert numpy array → WAV via soundfile → POST to API
- Parse JSON response for transcription text

**Local mode (`LocalSTT`):**
- Placeholder — raise NotImplementedError for now
- Will load Voxtral Realtime with transformers when GPU mode is ready

Factory function: `create_stt(config) -> STTEngine`

### 3. `voice/tts.py`

TTS with factory pattern. Abstract base class `TTSEngine` with `async def synthesize(text) -> np.ndarray`.

**API mode (`RivaTTSAPI`):**
- POST text to NVIDIA Riva TTS NIM API
- Parse WAV response back to numpy array
- Preprocess text before synthesis: strip markdown formatting, code blocks, links, limit to 1000 chars

**Local mode (`LocalTTS`):**
- Placeholder — raise NotImplementedError for now
- Will load FastPitch + HiFi-GAN from NeMo when GPU mode is ready

Factory function: `create_tts(config) -> TTSEngine`

### 4. `voice/pipeline.py`

State machine that ties VAD → STT → Orchestrator → TTS together.

**States:** `IDLE → LISTENING → PROCESSING → SPEAKING → IDLE`

**Pipeline class `VoicePipeline`:**
- Constructor takes: orchestrator, stt, tts, vad
- `async def feed_audio(chunk: bytes)` — called by WebSocket handler
  - Ignores audio while in SPEAKING state (no barge-in for hackathon)
  - Converts int16 PCM bytes → float32 numpy
  - Runs VAD on each chunk
  - On speech_start: transition to LISTENING, start buffering
  - On speech_end: call `_process_utterance()`
- `async def process_push_to_talk(audio_data: bytes)` — bypass VAD, process directly
- `async def _process_utterance()` — full pipeline:
  1. Set state to PROCESSING
  2. Concatenate audio buffer, reset VAD
  3. STT transcribe → get text
  4. Fire transcript callback
  5. Orchestrator.process(text) → get response
  6. Fire text response callback
  7. Set state to SPEAKING
  8. TTS synthesize → audio bytes
  9. Fire audio_out callback
  10. Set state to IDLE

**Callbacks (set by server):**
- `on_state_change(PipelineState)` — notify UI of state transitions
- `on_audio_out(bytes)` — send TTS audio to client
- `on_transcript(str, bool)` — send transcription (text, is_partial)
- `on_stream_chunk(StreamChunk)` — progressive updates

Audio format: 16kHz mono int16 PCM (input), 22.05kHz or 24kHz mono int16 PCM (output)

## Verification

```python
import asyncio
import numpy as np
from core.config import load_config
from voice.vad import SileroVAD
from voice.stt import create_stt
from voice.tts import create_tts

async def test():
    config = load_config()

    # Test VAD
    vad = SileroVAD(threshold=config.vad.threshold)
    silence = np.zeros(480, dtype=np.float32)
    result = vad.process_chunk(silence)
    print(f"VAD silence: {result}")

    # Test TTS (API mode)
    tts = await create_tts(config.tts)
    audio = await tts.synthesize("Hello, I am VoxaOS.")
    print(f"TTS output: {audio.shape} samples")

asyncio.run(test())
```

## Notes

- STT and TTS API endpoints/formats may need adjustment based on actual Mistral and NVIDIA docs. Verify exact schemas.
- Both are behind factory functions — easy to swap implementations without touching the pipeline.

## Quality Gate

### Test file: `tests/test_voice.py`

```python
import pytest
import numpy as np
from unittest.mock import AsyncMock, MagicMock
from core.types import PipelineState
from core.config import load_config

def test_vad_silence():
    """VAD should not detect speech in silence."""
    from voice.vad import SileroVAD
    vad = SileroVAD(threshold=0.5)
    silence = np.zeros(480, dtype=np.float32)
    result = vad.process_chunk(silence)
    assert result["is_speech"] is False
    assert result["speech_start"] is False

def test_vad_reset():
    from voice.vad import SileroVAD
    vad = SileroVAD(threshold=0.5)
    vad.process_chunk(np.zeros(480, dtype=np.float32))
    vad.reset()
    # Should not raise after reset

def test_stt_factory():
    """Factory should return correct backend."""
    from voice.stt import create_stt
    config = load_config()
    # Just verify the factory runs — actual transcription needs API key
    import asyncio
    stt = asyncio.get_event_loop().run_until_complete(create_stt(config.stt))
    assert stt is not None

def test_tts_factory():
    """Factory should return correct backend."""
    from voice.tts import create_tts
    config = load_config()
    import asyncio
    tts = asyncio.get_event_loop().run_until_complete(create_tts(config.tts))
    assert tts is not None

@pytest.mark.asyncio
async def test_pipeline_initial_state():
    """Pipeline should start in IDLE state."""
    from voice.pipeline import VoicePipeline
    mock_orch = MagicMock()
    mock_stt = MagicMock()
    mock_tts = MagicMock()
    mock_vad = MagicMock()
    pipeline = VoicePipeline(
        orchestrator=mock_orch, stt=mock_stt, tts=mock_tts, vad=mock_vad
    )
    assert pipeline.state == PipelineState.IDLE

@pytest.mark.asyncio
async def test_pipeline_feed_audio_calls_vad():
    """Feeding audio should run VAD processing."""
    from voice.pipeline import VoicePipeline
    mock_vad = MagicMock()
    mock_vad.process_chunk.return_value = {
        "is_speech": False, "speech_start": False,
        "speech_end": False, "speech_prob": 0.0,
    }
    pipeline = VoicePipeline(
        orchestrator=MagicMock(), stt=MagicMock(),
        tts=MagicMock(), vad=mock_vad,
    )
    # 480 samples of silence as int16 bytes
    chunk = np.zeros(480, dtype=np.int16).tobytes()
    await pipeline.feed_audio(chunk)
    assert mock_vad.process_chunk.called
```

### Run

```bash
ruff check voice/ tests/test_voice.py
mypy voice/vad.py voice/stt.py voice/tts.py voice/pipeline.py
pytest tests/test_voice.py -v
```

| Check | Command | Pass? |
|-------|---------|-------|
| Lint clean | `ruff check voice/ tests/test_voice.py` | |
| Types pass | `mypy voice/vad.py voice/pipeline.py` | |
| VAD silence test | `pytest tests/test_voice.py::test_vad_silence` | |
| Pipeline state | `pytest tests/test_voice.py::test_pipeline_initial_state` | |
| Factories create objects | `pytest tests/test_voice.py -k factory` | |

**Note:** STT/TTS API calls require keys — those are tested in the verification section manually. Unit tests use mocks.

## Design reference

See PLAN.md sections: "Voice Pipeline State Machine", Phase 3 implementation details, "Deployment Modes" (factory pattern for backends)

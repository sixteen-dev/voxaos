from unittest.mock import MagicMock

import numpy as np
import pytest

from core.config import load_config
from core.types import PipelineState
from voice.tts import preprocess_tts_text


def test_vad_silence():
    from voice.vad import SileroVAD

    vad = SileroVAD(threshold=0.5)
    silence = np.zeros(512, dtype=np.float32)
    result = vad.process_chunk(silence)
    assert result["is_speech"] is False
    assert result["speech_start"] is False


def test_vad_reset():
    from voice.vad import SileroVAD

    vad = SileroVAD(threshold=0.5)
    vad.process_chunk(np.zeros(512, dtype=np.float32))
    vad.reset()
    assert vad._speech_frames == 0
    assert vad._silence_frames == 0
    assert vad._in_speech is False


@pytest.mark.asyncio
async def test_stt_factory():
    from voice.stt import create_stt

    config = load_config()
    stt = await create_stt(config.stt)
    assert stt is not None


@pytest.mark.asyncio
async def test_tts_factory():
    from voice.tts import create_tts

    config = load_config()
    tts = await create_tts(config.tts)
    assert tts is not None


def test_preprocess_tts_strips_code_blocks():
    text = "Here is code:\n```python\nprint('hi')\n```\nDone."
    result = preprocess_tts_text(text)
    assert "print" not in result
    assert "code block omitted" in result


def test_preprocess_tts_strips_markdown():
    text = "**bold** and *italic* and [link](http://example.com)"
    result = preprocess_tts_text(text)
    assert "**" not in result
    assert "*" not in result
    assert "http" not in result
    assert "bold" in result
    assert "link" in result


def test_preprocess_tts_truncates():
    text = "x" * 2000
    result = preprocess_tts_text(text, max_chars=100)
    assert len(result) <= 104  # 100 + "..."


@pytest.mark.asyncio
async def test_pipeline_initial_state():
    from voice.pipeline import VoicePipeline

    pipeline = VoicePipeline(
        orchestrator=MagicMock(),
        stt=MagicMock(),
        tts=MagicMock(),
        vad=MagicMock(),
    )
    assert pipeline.state == PipelineState.IDLE


@pytest.mark.asyncio
async def test_pipeline_feed_audio_calls_vad():
    from voice.pipeline import VoicePipeline

    mock_vad = MagicMock()
    mock_vad.process_chunk.return_value = {
        "is_speech": False,
        "speech_start": False,
        "speech_end": False,
        "speech_prob": 0.0,
    }
    pipeline = VoicePipeline(
        orchestrator=MagicMock(),
        stt=MagicMock(),
        tts=MagicMock(),
        vad=mock_vad,
    )
    # 480 samples of silence as int16 bytes
    chunk = np.zeros(512, dtype=np.int16).tobytes()
    await pipeline.feed_audio(chunk)
    assert mock_vad.process_chunk.called


@pytest.mark.asyncio
async def test_pipeline_ignores_audio_while_speaking():
    from voice.pipeline import VoicePipeline

    mock_vad = MagicMock()
    pipeline = VoicePipeline(
        orchestrator=MagicMock(),
        stt=MagicMock(),
        tts=MagicMock(),
        vad=mock_vad,
    )
    pipeline.state = PipelineState.SPEAKING
    chunk = np.zeros(512, dtype=np.int16).tobytes()
    await pipeline.feed_audio(chunk)
    # VAD should NOT be called when speaking
    assert not mock_vad.process_chunk.called


@pytest.mark.asyncio
async def test_pipeline_ignores_audio_while_processing():
    from voice.pipeline import VoicePipeline

    mock_vad = MagicMock()
    pipeline = VoicePipeline(
        orchestrator=MagicMock(),
        stt=MagicMock(),
        tts=MagicMock(),
        vad=mock_vad,
    )
    pipeline.state = PipelineState.PROCESSING
    chunk = np.zeros(512, dtype=np.int16).tobytes()
    await pipeline.feed_audio(chunk)
    assert not mock_vad.process_chunk.called

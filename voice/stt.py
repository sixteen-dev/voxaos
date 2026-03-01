import io
import os
from abc import ABC, abstractmethod

import httpx
import numpy as np
import soundfile as sf  # type: ignore[import-untyped]

from core.config import STTConfig


class STTEngine(ABC):
    @abstractmethod
    async def transcribe(self, audio: np.ndarray, sample_rate: int = 16000) -> str:
        """Transcribe audio to text."""


class MistralSTTAPI(STTEngine):
    """Mistral Voxtral API for speech-to-text."""

    def __init__(self, config: STTConfig):
        self.base_url = config.api.base_url
        self.api_key = os.environ.get(config.api.api_key_env, "")

    async def transcribe(self, audio: np.ndarray, sample_rate: int = 16000) -> str:
        # Convert numpy → WAV bytes
        wav_buffer = io.BytesIO()
        sf.write(wav_buffer, audio, sample_rate, format="WAV", subtype="PCM_16")
        wav_bytes = wav_buffer.getvalue()

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                self.base_url,
                headers={"Authorization": f"Bearer {self.api_key}"},
                files={"file": ("audio.wav", wav_bytes, "audio/wav")},
                data={"model": "voxtral-mini-latest"},
            )
            resp.raise_for_status()
            data = resp.json()
            text: str = data.get("text", "")
            return text


class LocalSTT(STTEngine):
    """Placeholder for local Voxtral Realtime inference."""

    async def transcribe(self, audio: np.ndarray, sample_rate: int = 16000) -> str:
        raise NotImplementedError("Local STT not yet implemented — use API mode")


async def create_stt(config: STTConfig) -> STTEngine:
    if config.backend == "api":
        return MistralSTTAPI(config)
    return LocalSTT()

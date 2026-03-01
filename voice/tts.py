import io
import os
import re
from abc import ABC, abstractmethod

import httpx
import numpy as np
import soundfile as sf  # type: ignore[import-untyped]

from core.config import TTSConfig


class TTSEngine(ABC):
    @abstractmethod
    async def synthesize(self, text: str) -> np.ndarray:
        """Synthesize text to audio."""


def preprocess_tts_text(text: str, max_chars: int = 1000) -> str:
    """Clean text for TTS: strip markdown, code blocks, links."""
    # Remove code blocks
    text = re.sub(r"```[\s\S]*?```", " [code block omitted] ", text)
    # Remove inline code
    text = re.sub(r"`[^`]+`", "", text)
    # Remove markdown links, keep text
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    # Remove markdown bold/italic
    text = re.sub(r"[*_]{1,3}([^*_]+)[*_]{1,3}", r"\1", text)
    # Remove headers
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    # Truncate
    if len(text) > max_chars:
        text = text[:max_chars] + "..."
    return text


class RivaTTSAPI(TTSEngine):
    """NVIDIA Riva TTS NIM API for text-to-speech."""

    def __init__(self, config: TTSConfig):
        self.base_url = config.api.base_url
        self.api_key = os.environ.get(config.api.api_key_env, "")
        self.voice = config.api.voice

    async def synthesize(self, text: str) -> np.ndarray:
        text = preprocess_tts_text(text)
        if not text:
            return np.zeros(0, dtype=np.float32)

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{self.base_url}/audio/speech",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "input": text,
                    "voice": self.voice,
                    "response_format": "wav",
                },
            )
            resp.raise_for_status()

            # Parse WAV response to numpy
            wav_buffer = io.BytesIO(resp.content)
            audio: np.ndarray = sf.read(wav_buffer, dtype="float32")[0]
            return audio


class NoopTTS(TTSEngine):
    """Silent TTS that returns empty audio — used when TTS is disabled."""

    async def synthesize(self, text: str) -> np.ndarray:
        return np.zeros(0, dtype=np.float32)


class LocalTTS(TTSEngine):
    """Placeholder for local NeMo FastPitch + HiFi-GAN inference."""

    async def synthesize(self, text: str) -> np.ndarray:
        raise NotImplementedError("Local TTS not yet implemented — use API mode")


async def create_tts(config: TTSConfig) -> TTSEngine:
    if config.backend == "disabled":
        return NoopTTS()
    if config.backend == "api":
        return RivaTTSAPI(config)
    return LocalTTS()

import numpy as np
import torch


class SileroVAD:
    """Silero VAD wrapper. Runs on CPU, detects speech start/end."""

    def __init__(
        self,
        threshold: float = 0.5,
        speech_start_ms: int = 300,
        silence_end_ms: int = 500,
        sample_rate: int = 16000,
        chunk_ms: int = 32,
    ):
        self.threshold = threshold
        self.sample_rate = sample_rate
        # Silero VAD requires exactly 512 samples at 16kHz (32ms)
        self.chunk_size = 512 if sample_rate == 16000 else 256

        # Frames needed for start/end detection
        self._start_frames = int(speech_start_ms / chunk_ms)
        self._end_frames = int(silence_end_ms / chunk_ms)

        # State tracking
        self._speech_frames = 0
        self._silence_frames = 0
        self._in_speech = False

        # Load Silero VAD model
        self.model, _ = torch.hub.load(
            "snakers4/silero-vad",
            "silero_vad",
            trust_repo=True,
        )

    def process_chunk(self, audio_chunk: np.ndarray) -> dict:
        """Process a single audio chunk through VAD.

        Args:
            audio_chunk: float32 numpy array, 512 samples (32ms at 16kHz)

        Returns:
            dict with is_speech, speech_start, speech_end, speech_prob
        """
        tensor = torch.from_numpy(audio_chunk).float()
        if tensor.dim() == 1:
            tensor = tensor.unsqueeze(0)

        with torch.no_grad():
            prob = self.model(tensor, self.sample_rate).item()

        is_speech = prob >= self.threshold
        speech_start = False
        speech_end = False

        if is_speech:
            self._speech_frames += 1
            self._silence_frames = 0

            if not self._in_speech and self._speech_frames >= self._start_frames:
                self._in_speech = True
                speech_start = True
        else:
            self._silence_frames += 1
            self._speech_frames = 0

            if self._in_speech and self._silence_frames >= self._end_frames:
                self._in_speech = False
                speech_end = True

        return {
            "is_speech": is_speech,
            "speech_start": speech_start,
            "speech_end": speech_end,
            "speech_prob": prob,
        }

    def reset(self) -> None:
        self._speech_frames = 0
        self._silence_frames = 0
        self._in_speech = False
        self.model.reset_states()

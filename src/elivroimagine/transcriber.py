"""Whisper transcription using local model."""

import logging
from typing import Literal

import numpy as np
import whisper

from .config import WhisperConfig

logger = logging.getLogger(__name__)


class Transcriber:
    """Transcribes audio using local Whisper model."""

    def __init__(self, config: WhisperConfig) -> None:
        self.config = config
        self._model: whisper.Whisper | None = None
        self._model_size: str | None = None

    def _ensure_model(self) -> whisper.Whisper:
        """Load model if not already loaded or if size changed."""
        if self._model is None or self._model_size != self.config.model_size:
            logger.info(f"Loading Whisper model: {self.config.model_size}")
            self._model = whisper.load_model(self.config.model_size)
            self._model_size = self.config.model_size
            logger.info("Whisper model loaded")
        return self._model

    def transcribe(self, audio: np.ndarray, sample_rate: int = 16000) -> str:
        """Transcribe audio to text.

        Args:
            audio: Audio data as numpy array (float32, mono).
            sample_rate: Sample rate of the audio (default 16000).

        Returns:
            Transcribed text.
        """
        model = self._ensure_model()

        # Resample if needed (Whisper expects 16kHz)
        if sample_rate != 16000:
            # Simple resampling - for better quality, consider using librosa
            ratio = 16000 / sample_rate
            new_length = int(len(audio) * ratio)
            indices = np.linspace(0, len(audio) - 1, new_length).astype(int)
            audio = audio[indices]

        # Normalize audio
        audio = audio.astype(np.float32)
        if audio.max() > 1.0 or audio.min() < -1.0:
            audio = audio / max(abs(audio.max()), abs(audio.min()))

        # Transcribe
        options = {
            "fp16": False,  # Use float32 for CPU compatibility
        }
        if self.config.language:
            options["language"] = self.config.language

        result = model.transcribe(audio, **options)
        return result["text"].strip()

    def update_config(self, config: WhisperConfig) -> None:
        """Update configuration (will reload model if size changed)."""
        self.config = config

    @staticmethod
    def get_available_models() -> list[Literal["tiny", "base", "small", "medium"]]:
        """Get list of available model sizes."""
        return ["tiny", "base", "small", "medium"]

    @staticmethod
    def get_model_info(
        model_size: Literal["tiny", "base", "small", "medium"],
    ) -> dict[str, str]:
        """Get information about a model size."""
        info = {
            "tiny": {"size": "~39MB", "vram": "~1GB", "speed": "Fastest"},
            "base": {"size": "~74MB", "vram": "~1GB", "speed": "Fast"},
            "small": {"size": "~244MB", "vram": "~2GB", "speed": "Moderate"},
            "medium": {"size": "~769MB", "vram": "~5GB", "speed": "Slower"},
        }
        return info.get(model_size, {"size": "Unknown", "vram": "Unknown", "speed": "Unknown"})

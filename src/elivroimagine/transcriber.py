"""Whisper transcription using faster-whisper (CTranslate2 backend) or Berget.ai API."""

from __future__ import annotations

import io
import logging
import threading
import wave
from abc import ABC, abstractmethod
from concurrent.futures import Future, ThreadPoolExecutor, TimeoutError
from typing import TYPE_CHECKING, Callable, Literal, Protocol

import numpy as np

from .config import SUPPORTED_LANGUAGES, TranscriptionConfig, WhisperConfig

if TYPE_CHECKING:
    from faster_whisper import WhisperModel

logger = logging.getLogger(__name__)


class TranscriptionError(Exception):
    """Raised when audio transcription fails."""

    pass


class TranscriptionTimeoutError(TranscriptionError):
    """Raised when transcription exceeds the configured timeout."""

    pass


class APIError(TranscriptionError):
    """Raised for API-specific errors (auth, rate limit, network)."""

    pass


class APIKeyMissingError(TranscriptionError):
    """Raised when API key is not configured."""

    pass


class TranscriptionBackend(Protocol):
    """Protocol for transcription backends."""

    def transcribe(self, audio: np.ndarray, sample_rate: int) -> str:
        """Transcribe audio to text."""
        ...

    def update_config(self, config: WhisperConfig) -> None:
        """Update configuration."""
        ...


class LocalTranscriber:
    """Transcribes audio using local faster-whisper model."""

    def __init__(
        self,
        config: WhisperConfig,
        on_progress: Callable[[str], None] | None = None,
    ) -> None:
        self.config = config
        self._model: object | None = None
        self._model_size: str | None = None
        self._model_lock = threading.Lock()
        self._on_progress = on_progress

    def _get_device_and_compute(self) -> tuple[str, str]:
        """Get the best available device and compute type for inference.

        Returns:
            Tuple of (device, compute_type).
        """
        try:
            import ctranslate2
            # If get_supported_compute_types("cuda") succeeds, CUDA is available
            supported = ctranslate2.get_supported_compute_types("cuda")
            if "float16" in supported:
                return "cuda", "float16"
            return "cuda", "int8"
        except Exception:
            pass
        return "cpu", "int8"

    def _ensure_model(self) -> object:
        """Load model if not already loaded or if size changed."""
        import gc

        with self._model_lock:
            if self._model is None or self._model_size != self.config.model_size:
                # Free old model before loading new one
                if self._model is not None:
                    del self._model
                    self._model = None
                    gc.collect()  # Force garbage collection to release CUDA memory

                device, compute_type = self._get_device_and_compute()
                logger.info(
                    f"Loading Whisper model: {self.config.model_size} "
                    f"on {device} ({compute_type})"
                )

                if self._on_progress:
                    self._on_progress(
                        f"Loading Whisper model ({self.config.model_size})..."
                    )

                from faster_whisper import WhisperModel

                try:
                    self._model = WhisperModel(
                        self.config.model_size,
                        device=device,
                        compute_type=compute_type,
                    )
                except Exception as cuda_err:
                    if device == "cuda":
                        logger.warning(
                            f"CUDA load failed ({cuda_err}), "
                            "falling back to CPU"
                        )
                        if self._on_progress:
                            self._on_progress(
                                "CUDA unavailable, using CPU..."
                            )
                        device, compute_type = "cpu", "int8"
                        self._model = WhisperModel(
                            self.config.model_size,
                            device=device,
                            compute_type=compute_type,
                        )
                    else:
                        raise

                self._model_size = self.config.model_size
                logger.info("Whisper model loaded")

                if self._on_progress:
                    self._on_progress("Whisper model ready")

            return self._model

    def _do_transcribe(self, audio: np.ndarray, model: object) -> str:
        """Perform the actual transcription (called in thread for timeout)."""
        # Normalize audio
        audio = audio.astype(np.float32)
        if audio.max() > 1.0 or audio.min() < -1.0:
            audio = audio / max(abs(audio.max()), abs(audio.min()))

        # Build transcribe kwargs - omit language for auto-detection
        transcribe_kwargs = {
            "beam_size": 5,
            "vad_filter": True,
        }
        if self.config.language != "auto":
            transcribe_kwargs["language"] = self.config.language

        # Transcribe with faster-whisper
        segments, info = model.transcribe(audio, **transcribe_kwargs)

        # Collect all segment texts
        text = " ".join(segment.text.strip() for segment in segments)
        return text.strip()

    def _run_with_timeout(
        self, audio: np.ndarray, model: object
    ) -> str:
        """Run transcription with timeout."""
        executor = ThreadPoolExecutor(max_workers=1)
        try:
            timeout = self.config.transcription_timeout_seconds
            future: Future[str] = executor.submit(
                self._do_transcribe, audio, model
            )
            try:
                return future.result(timeout=timeout)
            except TimeoutError:
                logger.error(
                    f"Transcription timed out after {timeout}s"
                )
                executor.shutdown(wait=False, cancel_futures=True)
                raise TranscriptionTimeoutError(
                    f"Transcription timed out after {timeout} seconds"
                )
        finally:
            executor.shutdown(wait=False)

    def _is_cuda_runtime_error(self, error: Exception) -> bool:
        """Check if an error is caused by missing CUDA runtime libraries."""
        msg = str(error).lower()
        return any(
            indicator in msg
            for indicator in ("cublas", "cudnn", "cudart", "cuda", "nvcuda")
        )

    def _force_cpu_model(self) -> object:
        """Discard the current model and reload on CPU."""
        with self._model_lock:
            del self._model
            self._model = None
            self._model_size = None

            logger.warning("Reloading Whisper model on CPU after CUDA runtime failure")
            if self._on_progress:
                self._on_progress("CUDA failed at runtime, reloading on CPU...")

            from faster_whisper import WhisperModel

            self._model = WhisperModel(
                self.config.model_size,
                device="cpu",
                compute_type="int8",
            )
            self._model_size = self.config.model_size
            logger.info("Whisper model reloaded on CPU")

            if self._on_progress:
                self._on_progress("Whisper model ready (CPU)")

            return self._model

    def transcribe(self, audio: np.ndarray, sample_rate: int = 16000) -> str:
        """Transcribe audio to text with timeout.

        Args:
            audio: Audio data as numpy array (float32, mono).
            sample_rate: Sample rate of the audio (default 16000).

        Returns:
            Transcribed text.

        Raises:
            TranscriptionError: If transcription fails.
            TranscriptionTimeoutError: If transcription exceeds timeout.
        """
        # Load model outside the timeout — download/load can take minutes
        # on first run but should not cause a timeout error
        try:
            model = self._ensure_model()
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            raise TranscriptionError(f"Failed to load Whisper model: {e}") from e

        try:
            return self._run_with_timeout(audio, model)
        except TranscriptionTimeoutError:
            raise
        except Exception as e:
            # If CUDA libs are missing at runtime (e.g. cublas64_12.dll),
            # the model loaded fine but inference fails. Reload on CPU and retry.
            if self._is_cuda_runtime_error(e):
                logger.warning(f"CUDA runtime error during inference: {e}")
                try:
                    cpu_model = self._force_cpu_model()
                    return self._run_with_timeout(audio, cpu_model)
                except TranscriptionTimeoutError:
                    raise
                except Exception as cpu_err:
                    logger.error(f"CPU transcription also failed: {cpu_err}")
                    raise TranscriptionError(
                        f"Failed to transcribe audio: {cpu_err}"
                    ) from cpu_err

            logger.error(f"Transcription failed: {e}")
            raise TranscriptionError(f"Failed to transcribe audio: {e}") from e

    def update_config(self, config: WhisperConfig) -> None:
        """Update configuration (will reload model if size changed)."""
        self.config = config

    @staticmethod
    def get_available_models() -> list[Literal["tiny", "base", "small", "medium", "large"]]:
        """Get list of available model sizes."""
        return ["tiny", "base", "small", "medium", "large"]

    @staticmethod
    def get_available_languages() -> list[tuple[str, str]]:
        """Get list of supported languages as (code, name) tuples."""
        return SUPPORTED_LANGUAGES

    @staticmethod
    def get_model_info(
        model_size: Literal["tiny", "base", "small", "medium", "large"],
    ) -> dict[str, str]:
        """Get information about a model size."""
        info = {
            "tiny": {"size": "~39MB", "vram": "~1GB", "speed": "Fastest"},
            "base": {"size": "~74MB", "vram": "~1GB", "speed": "Fast"},
            "small": {"size": "~244MB", "vram": "~2GB", "speed": "Moderate"},
            "medium": {"size": "~769MB", "vram": "~5GB", "speed": "Slower"},
            "large": {"size": "~1.5GB", "vram": "~10GB", "speed": "Slowest"},
        }
        return info.get(model_size, {"size": "Unknown", "vram": "Unknown", "speed": "Unknown"})


class BergetTranscriber:
    """Transcribes audio using Berget.ai API (OpenAI-compatible endpoint)."""

    API_URL = "https://api.berget.ai/v1/audio/transcriptions"
    MODEL = "KBLab/kb-whisper-large"

    def __init__(
        self,
        api_key: str,
        config: WhisperConfig,
        on_progress: Callable[[str], None] | None = None,
    ) -> None:
        self.api_key = api_key
        self.config = config
        self._on_progress = on_progress

    def _audio_to_wav_bytes(self, audio: np.ndarray, sample_rate: int) -> bytes:
        """Convert numpy audio array to WAV bytes."""
        # Normalize audio
        audio = audio.astype(np.float32)
        if audio.max() > 1.0 or audio.min() < -1.0:
            audio = audio / max(abs(audio.max()), abs(audio.min()))

        # Convert to 16-bit PCM
        audio_int16 = (audio * 32767).astype(np.int16)

        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)  # 16-bit
            wf.setframerate(sample_rate)
            wf.writeframes(audio_int16.tobytes())
        buffer.seek(0)
        return buffer.read()

    def transcribe(self, audio: np.ndarray, sample_rate: int = 16000) -> str:
        """Transcribe audio to text using Berget.ai API with streaming.

        Args:
            audio: Audio data as numpy array (float32, mono).
            sample_rate: Sample rate of the audio (default 16000).

        Returns:
            Transcribed text.

        Raises:
            APIKeyMissingError: If API key is not configured.
            APIError: If API request fails.
            TranscriptionTimeoutError: If request times out.
        """
        if not self.api_key:
            raise APIKeyMissingError("Berget.ai API key not configured")

        import json

        import requests

        if self._on_progress:
            self._on_progress("Transcribing...")

        wav_bytes = self._audio_to_wav_bytes(audio, sample_rate)

        # Build request data with streaming enabled
        request_data: dict[str, str | bool] = {
            "model": self.MODEL,
            "stream": "true",  # Enable SSE streaming
        }
        if self.config.language != "auto":
            request_data["language"] = self.config.language
        if self.config.language == "en":
            request_data["prompt"] = "Transcribe the following audio in English."

        try:
            # Use stream=True for SSE response
            response = requests.post(
                self.API_URL,
                headers={"Authorization": f"Bearer {self.api_key}"},
                files={"file": ("audio.wav", wav_bytes, "audio/wav")},
                data=request_data,
                timeout=self.config.transcription_timeout_seconds,
                stream=True,  # Enable response streaming
            )
        except requests.Timeout:
            logger.error(
                f"Berget.ai API timed out after "
                f"{self.config.transcription_timeout_seconds}s"
            )
            raise TranscriptionTimeoutError(
                f"API request timed out after "
                f"{self.config.transcription_timeout_seconds} seconds"
            )
        except requests.ConnectionError as e:
            logger.error(f"Could not connect to Berget.ai: {e}")
            raise APIError("Could not connect to Berget.ai") from e
        except requests.RequestException as e:
            logger.error(f"Berget.ai API request failed: {e}")
            raise APIError(f"API request failed: {e}") from e

        if response.status_code == 401:
            logger.error("Invalid Berget.ai API key")
            raise APIError("Invalid Berget.ai API key")
        if response.status_code == 429:
            logger.error("Berget.ai rate limit exceeded")
            raise APIError("Berget.ai rate limit exceeded, try again later")
        if response.status_code != 200:
            logger.error(
                f"Berget.ai API error: {response.status_code} - {response.text}"
            )
            raise APIError(f"API error: {response.status_code}")

        # Parse SSE stream or fall back to regular JSON
        text_parts: list[str] = []
        content_type = response.headers.get("content-type", "")

        if "text/event-stream" in content_type:
            # SSE streaming response
            for line in response.iter_lines(decode_unicode=True):
                if not line:
                    continue
                if line.startswith("data: "):
                    data = line[6:]  # Remove "data: " prefix
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                        # Handle different response formats
                        if "text" in chunk:
                            text_parts.append(chunk["text"])
                        elif "delta" in chunk:
                            text_parts.append(chunk["delta"].get("text", ""))
                        elif "choices" in chunk:
                            # OpenAI-style streaming
                            for choice in chunk.get("choices", []):
                                delta = choice.get("delta", {})
                                if "content" in delta:
                                    text_parts.append(delta["content"])
                    except json.JSONDecodeError:
                        continue
            text = "".join(text_parts).strip()
        else:
            # Regular JSON response (fallback)
            try:
                result = response.json()
                text = result.get("text", "").strip()
            except ValueError as e:
                logger.error(f"Failed to parse Berget.ai response: {e}")
                raise APIError("Invalid response from Berget.ai") from e

        if self._on_progress:
            self._on_progress("Done")

        return text

    def update_config(self, config: WhisperConfig) -> None:
        """Update configuration."""
        self.config = config

    def update_api_key(self, api_key: str) -> None:
        """Update the API key."""
        self.api_key = api_key


class Transcriber:
    """Facade that delegates to the active transcription backend."""

    def __init__(
        self,
        config: WhisperConfig,
        transcription_config: TranscriptionConfig | None = None,
        on_progress: Callable[[str], None] | None = None,
    ) -> None:
        self.config = config
        self.transcription_config = transcription_config or TranscriptionConfig()
        self._on_progress = on_progress
        self._backend_lock = threading.Lock()  # Protect backend switching
        self._backend: LocalTranscriber | BergetTranscriber = self._create_backend()

    def _create_backend(self) -> LocalTranscriber | BergetTranscriber:
        """Create the appropriate backend based on config."""
        if self.transcription_config.backend == "berget":
            return BergetTranscriber(
                api_key=self.transcription_config.berget_api_key,
                config=self.config,
                on_progress=self._on_progress,
            )
        return LocalTranscriber(
            config=self.config,
            on_progress=self._on_progress,
        )

    def transcribe(self, audio: np.ndarray, sample_rate: int = 16000) -> str:
        """Transcribe audio to text using the active backend.

        Args:
            audio: Audio data as numpy array (float32, mono).
            sample_rate: Sample rate of the audio (default 16000).

        Returns:
            Transcribed text.

        Raises:
            TranscriptionError: If transcription fails.
            TranscriptionTimeoutError: If transcription exceeds timeout.
            APIError: If API backend fails.
            APIKeyMissingError: If API key is missing for API backend.
        """
        with self._backend_lock:
            backend = self._backend
        return backend.transcribe(audio, sample_rate)

    def update_config(self, config: WhisperConfig) -> None:
        """Update Whisper configuration (will reload model if size changed)."""
        self.config = config
        self._backend.update_config(config)

    def update_transcription_config(self, config: TranscriptionConfig) -> None:
        """Update transcription backend configuration.

        Recreates backend if backend type changed.
        """
        with self._backend_lock:
            old_backend = self.transcription_config.backend
            self.transcription_config = config

            if old_backend != config.backend:
                # Backend type changed, recreate
                self._backend = self._create_backend()
            elif config.backend == "berget" and isinstance(self._backend, BergetTranscriber):
                # Same backend, update API key
                self._backend.update_api_key(config.berget_api_key)

    def _ensure_model(self) -> object:
        """Ensure model is loaded (for pre-loading). Only works with local backend."""
        if isinstance(self._backend, LocalTranscriber):
            return self._backend._ensure_model()
        return None

    @staticmethod
    def get_available_models() -> list[Literal["tiny", "base", "small", "medium", "large"]]:
        """Get list of available model sizes."""
        return LocalTranscriber.get_available_models()

    @staticmethod
    def get_available_languages() -> list[tuple[str, str]]:
        """Get list of supported languages as (code, name) tuples."""
        return LocalTranscriber.get_available_languages()

    @staticmethod
    def get_model_info(
        model_size: Literal["tiny", "base", "small", "medium", "large"],
    ) -> dict[str, str]:
        """Get information about a model size."""
        return LocalTranscriber.get_model_info(model_size)

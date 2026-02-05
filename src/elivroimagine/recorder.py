"""Audio recording using sounddevice library."""

import logging
import threading
import time
from typing import Callable

import numpy as np
import sounddevice as sd

from .config import RecordingConfig

logger = logging.getLogger(__name__)


class AudioRecorder:
    """Records audio from the default microphone."""

    def __init__(self, config: RecordingConfig) -> None:
        self.config = config
        self._recording = False
        self._audio_data: list[np.ndarray] = []
        self._record_thread: threading.Thread | None = None
        self._start_time: float = 0.0
        self._on_status_change: Callable[[str], None] | None = None
        self._lock = threading.Lock()

    def set_status_callback(self, callback: Callable[[str], None]) -> None:
        """Set callback for status changes."""
        self._on_status_change = callback

    def _notify_status(self, status: str) -> None:
        """Notify status change."""
        if self._on_status_change:
            self._on_status_change(status)

    def start_recording(self) -> None:
        """Start recording audio."""
        with self._lock:
            if self._recording:
                return
            self._recording = True
            self._audio_data = []
            self._start_time = time.time()

        self._record_thread = threading.Thread(target=self._record_loop, daemon=True)
        self._record_thread.start()
        self._notify_status("recording")

    def stop_recording(self) -> tuple[np.ndarray, float] | None:
        """Stop recording and return audio data with duration.

        Returns:
            Tuple of (audio_data as numpy array, duration in seconds) or None if no data.
        """
        with self._lock:
            if not self._recording:
                return None
            self._recording = False
            duration = time.time() - self._start_time

        record_thread = self._record_thread
        if record_thread:
            record_thread.join(timeout=2.0)
            if record_thread.is_alive():
                logger.warning("Recording thread did not stop within timeout")
            self._record_thread = None

        self._notify_status("processing")

        with self._lock:
            if not self._audio_data:
                return None
            audio = np.concatenate(self._audio_data)
            self._audio_data = []  # Clear after use

        return audio, duration

    def _record_loop(self) -> None:
        """Recording loop that captures audio chunks."""
        device = None
        if self.config.microphone_id:
            device = int(self.config.microphone_id)

        chunk_size = int(self.config.sample_rate * 0.1)  # 100ms chunks

        # Try configured device, then fall back to default
        for attempt_device in ([device, None] if device is not None else [None]):
            try:
                with sd.InputStream(
                    device=attempt_device,
                    samplerate=self.config.sample_rate,
                    channels=1,
                    dtype=np.float32,
                    blocksize=chunk_size,
                ) as stream:
                    if attempt_device is None and device is not None:
                        logger.warning(
                            "Configured microphone unavailable, using default"
                        )
                        self._notify_status("warning: Using default microphone")

                    while True:
                        with self._lock:
                            if not self._recording:
                                break
                            elapsed = time.time() - self._start_time
                            if elapsed >= self.config.max_duration_seconds:
                                self._recording = False
                                break

                        data, overflowed = stream.read(chunk_size)
                        if data is not None and len(data) > 0:
                            # Flatten to mono if needed
                            if len(data.shape) > 1:
                                data = data[:, 0]
                            with self._lock:
                                self._audio_data.append(data.astype(np.float32))

                return  # Recording completed successfully

            except sd.PortAudioError as e:
                if attempt_device is not None:
                    logger.warning(
                        f"Microphone {attempt_device} failed: {e}. "
                        "Retrying with default device..."
                    )
                    continue
                # Default device also failed
                logger.error(f"Recording failed (no working microphone): {e}")
                self._notify_status("error: No working microphone found")
                with self._lock:
                    self._recording = False
                    self._audio_data = []
                return

            except Exception as e:
                logger.error(f"Recording error: {e}")
                self._notify_status(f"error: {e}")
                with self._lock:
                    self._recording = False
                    self._audio_data = []
                return

    @property
    def is_recording(self) -> bool:
        """Check if currently recording."""
        with self._lock:
            return self._recording

    def get_duration(self) -> float:
        """Get current recording duration in seconds."""
        with self._lock:
            if not self._recording:
                return 0.0
            return time.time() - self._start_time

    @staticmethod
    def get_available_microphones() -> list[dict[str, str]]:
        """Return list of available microphones with id and name.

        Returns:
            List of dicts with 'id' and 'name' keys for each microphone.
        """
        mics = []
        devices = sd.query_devices()
        for i, device in enumerate(devices):
            # Only include input devices
            if device["max_input_channels"] > 0:
                mics.append({"id": str(i), "name": device["name"]})
        return mics

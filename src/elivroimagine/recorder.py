"""Audio recording using soundcard library."""

import threading
import time
from typing import Callable

import numpy as np
import soundcard as sc

from .config import RecordingConfig


class AudioRecorder:
    """Records audio from the default microphone."""

    def __init__(self, config: RecordingConfig) -> None:
        self.config = config
        self._recording = False
        self._audio_data: list[np.ndarray] = []
        self._record_thread: threading.Thread | None = None
        self._start_time: float = 0.0
        self._on_status_change: Callable[[str], None] | None = None

    def set_status_callback(self, callback: Callable[[str], None]) -> None:
        """Set callback for status changes."""
        self._on_status_change = callback

    def _notify_status(self, status: str) -> None:
        """Notify status change."""
        if self._on_status_change:
            self._on_status_change(status)

    def start_recording(self) -> None:
        """Start recording audio."""
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
        if not self._recording:
            return None

        self._recording = False
        duration = time.time() - self._start_time

        if self._record_thread:
            self._record_thread.join(timeout=2.0)
            self._record_thread = None

        self._notify_status("processing")

        if not self._audio_data:
            return None

        audio = np.concatenate(self._audio_data)
        return audio, duration

    def _record_loop(self) -> None:
        """Recording loop that captures audio chunks."""
        try:
            mic = sc.default_microphone()
            chunk_size = int(self.config.sample_rate * 0.1)  # 100ms chunks

            with mic.recorder(
                samplerate=self.config.sample_rate,
                channels=1,
                blocksize=chunk_size,
            ) as recorder:
                while self._recording:
                    elapsed = time.time() - self._start_time
                    if elapsed >= self.config.max_duration_seconds:
                        self._recording = False
                        break

                    data = recorder.record(numframes=chunk_size)
                    if data is not None and len(data) > 0:
                        # Flatten to mono if needed
                        if len(data.shape) > 1:
                            data = data[:, 0]
                        self._audio_data.append(data.astype(np.float32))

        except Exception as e:
            self._notify_status(f"error: {e}")
            self._recording = False

    @property
    def is_recording(self) -> bool:
        """Check if currently recording."""
        return self._recording

    def get_duration(self) -> float:
        """Get current recording duration in seconds."""
        if not self._recording:
            return 0.0
        return time.time() - self._start_time

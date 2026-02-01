"""Tests for audio recording functionality."""

import time
from unittest.mock import MagicMock, patch

import numpy as np
import pytest


class TestRecorderStartStop:
    """Test recorder start/stop functionality."""

    def test_start_recording_sets_state(self, mock_soundcard: MagicMock) -> None:
        """Starting recording sets recording state."""
        from elivroimagine.config import RecordingConfig
        from elivroimagine.recorder import AudioRecorder

        config = RecordingConfig()
        recorder = AudioRecorder(config)

        recorder.start_recording()

        assert recorder.is_recording is True

        # Clean up
        recorder._recording = False
        time.sleep(0.2)

    def test_start_recording_only_once(self, mock_soundcard: MagicMock) -> None:
        """Starting recording when already recording is a no-op."""
        from elivroimagine.config import RecordingConfig
        from elivroimagine.recorder import AudioRecorder

        config = RecordingConfig()
        recorder = AudioRecorder(config)

        recorder.start_recording()
        first_thread = recorder._record_thread

        recorder.start_recording()
        second_thread = recorder._record_thread

        # Should be same thread, not a new one
        assert first_thread is second_thread

        # Clean up
        recorder._recording = False
        time.sleep(0.2)

    def test_stop_recording_returns_data(self, mock_soundcard: MagicMock) -> None:
        """Stopping recording returns audio data and duration."""
        from elivroimagine.config import RecordingConfig
        from elivroimagine.recorder import AudioRecorder

        config = RecordingConfig()
        recorder = AudioRecorder(config)

        # Manually set up state as if we had recorded
        recorder._recording = True
        recorder._start_time = time.time() - 1.0
        recorder._audio_data = [np.array([0.1, 0.2, 0.3], dtype=np.float32)]

        result = recorder.stop_recording()

        assert result is not None
        audio, duration = result
        assert isinstance(audio, np.ndarray)
        assert duration >= 1.0

    def test_stop_recording_when_not_recording(
        self, mock_soundcard: MagicMock
    ) -> None:
        """Stopping when not recording returns None."""
        from elivroimagine.config import RecordingConfig
        from elivroimagine.recorder import AudioRecorder

        config = RecordingConfig()
        recorder = AudioRecorder(config)

        result = recorder.stop_recording()

        assert result is None

    def test_stop_recording_with_no_data(self, mock_soundcard: MagicMock) -> None:
        """Stopping with no data returns None."""
        from elivroimagine.config import RecordingConfig
        from elivroimagine.recorder import AudioRecorder

        config = RecordingConfig()
        recorder = AudioRecorder(config)

        recorder._recording = True
        recorder._start_time = time.time()
        recorder._audio_data = []

        result = recorder.stop_recording()

        assert result is None


class TestRecorderDuration:
    """Test recording duration tracking."""

    def test_get_duration_when_recording(self, mock_soundcard: MagicMock) -> None:
        """get_duration returns elapsed time when recording."""
        from elivroimagine.config import RecordingConfig
        from elivroimagine.recorder import AudioRecorder

        config = RecordingConfig()
        recorder = AudioRecorder(config)

        recorder._recording = True
        recorder._start_time = time.time() - 2.5

        duration = recorder.get_duration()

        assert duration >= 2.5

    def test_get_duration_when_not_recording(
        self, mock_soundcard: MagicMock
    ) -> None:
        """get_duration returns 0 when not recording."""
        from elivroimagine.config import RecordingConfig
        from elivroimagine.recorder import AudioRecorder

        config = RecordingConfig()
        recorder = AudioRecorder(config)

        duration = recorder.get_duration()

        assert duration == 0.0


class TestRecorderStatusCallback:
    """Test recorder status callbacks."""

    def test_status_callback_on_start(self, mock_soundcard: MagicMock) -> None:
        """Status callback fires on start."""
        from elivroimagine.config import RecordingConfig
        from elivroimagine.recorder import AudioRecorder

        config = RecordingConfig()
        recorder = AudioRecorder(config)

        status_callback = MagicMock()
        recorder.set_status_callback(status_callback)

        recorder.start_recording()
        time.sleep(0.1)

        status_callback.assert_called_with("recording")

        # Clean up
        recorder._recording = False
        time.sleep(0.2)

    def test_status_callback_on_stop(self, mock_soundcard: MagicMock) -> None:
        """Status callback fires 'processing' on stop."""
        from elivroimagine.config import RecordingConfig
        from elivroimagine.recorder import AudioRecorder

        config = RecordingConfig()
        recorder = AudioRecorder(config)

        status_callback = MagicMock()
        recorder.set_status_callback(status_callback)

        # Set up recorded state
        recorder._recording = True
        recorder._start_time = time.time()
        recorder._audio_data = [np.array([0.1], dtype=np.float32)]

        recorder.stop_recording()

        # Should have been called with 'processing'
        status_callback.assert_called_with("processing")


class TestRecorderConfig:
    """Test recorder configuration."""

    def test_uses_config_sample_rate(self, mock_soundcard: MagicMock) -> None:
        """Recorder uses sample rate from config."""
        from elivroimagine.config import RecordingConfig
        from elivroimagine.recorder import AudioRecorder

        config = RecordingConfig(sample_rate=48000)
        recorder = AudioRecorder(config)

        assert recorder.config.sample_rate == 48000

    def test_uses_config_max_duration(self, mock_soundcard: MagicMock) -> None:
        """Recorder uses max duration from config."""
        from elivroimagine.config import RecordingConfig
        from elivroimagine.recorder import AudioRecorder

        config = RecordingConfig(max_duration_seconds=60)
        recorder = AudioRecorder(config)

        assert recorder.config.max_duration_seconds == 60

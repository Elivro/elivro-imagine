"""Tests for audio recording functionality."""

import time
from unittest.mock import MagicMock, patch

import numpy as np
import pytest


class TestRecorderStartStop:
    """Test recorder start/stop functionality."""

    def test_start_recording_sets_state(self, mock_sounddevice: MagicMock) -> None:
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

    def test_start_recording_only_once(self, mock_sounddevice: MagicMock) -> None:
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

    def test_stop_recording_returns_data(self, mock_sounddevice: MagicMock) -> None:
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
        self, mock_sounddevice: MagicMock
    ) -> None:
        """Stopping when not recording returns None."""
        from elivroimagine.config import RecordingConfig
        from elivroimagine.recorder import AudioRecorder

        config = RecordingConfig()
        recorder = AudioRecorder(config)

        result = recorder.stop_recording()

        assert result is None

    def test_stop_recording_with_no_data(self, mock_sounddevice: MagicMock) -> None:
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

    def test_get_duration_when_recording(self, mock_sounddevice: MagicMock) -> None:
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
        self, mock_sounddevice: MagicMock
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

    def test_status_callback_on_start(self, mock_sounddevice: MagicMock) -> None:
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

    def test_status_callback_on_stop(self, mock_sounddevice: MagicMock) -> None:
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

    def test_uses_config_sample_rate(self, mock_sounddevice: MagicMock) -> None:
        """Recorder uses sample rate from config."""
        from elivroimagine.config import RecordingConfig
        from elivroimagine.recorder import AudioRecorder

        config = RecordingConfig(sample_rate=48000)
        recorder = AudioRecorder(config)

        assert recorder.config.sample_rate == 48000

    def test_uses_config_max_duration(self, mock_sounddevice: MagicMock) -> None:
        """Recorder uses max duration from config."""
        from elivroimagine.config import RecordingConfig
        from elivroimagine.recorder import AudioRecorder

        config = RecordingConfig(max_duration_seconds=60)
        recorder = AudioRecorder(config)

        assert recorder.config.max_duration_seconds == 60


class TestRecorderThreadSafety:
    """Test recorder thread safety."""

    def test_recorder_has_lock(self, mock_sounddevice: MagicMock) -> None:
        """Recorder has a threading lock."""
        import threading

        from elivroimagine.config import RecordingConfig
        from elivroimagine.recorder import AudioRecorder

        config = RecordingConfig()
        recorder = AudioRecorder(config)

        assert hasattr(recorder, "_lock")
        assert isinstance(recorder._lock, type(threading.Lock()))

    def test_concurrent_start_stop(self, mock_sounddevice: MagicMock) -> None:
        """Concurrent start/stop operations don't corrupt state."""
        import threading

        from elivroimagine.config import RecordingConfig
        from elivroimagine.recorder import AudioRecorder

        config = RecordingConfig()
        recorder = AudioRecorder(config)

        # Run multiple concurrent operations - the key is no deadlocks or crashes
        def start_stop():
            for _ in range(5):
                recorder.start_recording()
                time.sleep(0.01)
                recorder.stop_recording()

        threads = [threading.Thread(target=start_stop) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5.0)

        # All threads should complete (no deadlock)
        for t in threads:
            assert not t.is_alive(), "Thread deadlocked"

        # Final state should be not recording
        assert recorder.is_recording is False

    def test_stop_recording_clears_audio_data(
        self, mock_sounddevice: MagicMock
    ) -> None:
        """Stop recording clears audio data after returning it."""
        from elivroimagine.config import RecordingConfig
        from elivroimagine.recorder import AudioRecorder

        config = RecordingConfig()
        recorder = AudioRecorder(config)

        # Manually set up state
        recorder._recording = True
        recorder._start_time = time.time() - 1.0
        recorder._audio_data = [np.array([0.1, 0.2], dtype=np.float32)]

        result = recorder.stop_recording()

        assert result is not None
        # Audio data should be cleared after stop
        assert recorder._audio_data == []

    def test_error_in_record_loop_clears_state(
        self, mock_sounddevice: MagicMock
    ) -> None:
        """Error in record loop clears recording state and audio data."""
        from elivroimagine.config import RecordingConfig
        from elivroimagine.recorder import AudioRecorder

        # Make InputStream raise an error
        mock_sounddevice.InputStream.side_effect = Exception("Test error")

        config = RecordingConfig()
        recorder = AudioRecorder(config)
        status_callback = MagicMock()
        recorder.set_status_callback(status_callback)

        recorder.start_recording()
        time.sleep(0.2)  # Allow thread to process

        # Recording should be stopped and data cleared
        assert recorder.is_recording is False
        assert recorder._audio_data == []
        # Error status should have been notified
        assert any("error" in str(call) for call in status_callback.call_args_list)

    def test_thread_timeout_warning(self, mock_sounddevice: MagicMock) -> None:
        """Thread that doesn't stop logs warning."""
        from unittest.mock import patch

        from elivroimagine.config import RecordingConfig
        from elivroimagine.recorder import AudioRecorder

        # Create a thread that won't stop
        config = RecordingConfig()
        recorder = AudioRecorder(config)

        # Manually set up a "stuck" thread
        recorder._recording = True
        recorder._start_time = time.time() - 1.0
        recorder._audio_data = [np.array([0.1], dtype=np.float32)]

        # Create a mock thread that's always alive
        mock_thread = MagicMock()
        mock_thread.join = MagicMock()
        mock_thread.is_alive.return_value = True
        recorder._record_thread = mock_thread

        with patch("elivroimagine.recorder.logger") as mock_logger:
            recorder.stop_recording()
            mock_logger.warning.assert_called()

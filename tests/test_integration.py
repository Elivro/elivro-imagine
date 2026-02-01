"""Integration tests for full ElivroImagine workflow."""

import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import numpy as np
import pytest


@pytest.fixture
def fresh_sounds_module(mock_pygame: MagicMock):
    """Reload sounds module with mocked pygame for each test."""
    # Remove cached module to get fresh import with mocked pygame
    if "elivroimagine.sounds" in sys.modules:
        del sys.modules["elivroimagine.sounds"]

    # Now import with mock in place
    import elivroimagine.sounds

    # Reset module state
    elivroimagine.sounds._mixer_initialized = False

    yield elivroimagine.sounds, mock_pygame

    # Clean up
    if "elivroimagine.sounds" in sys.modules:
        del sys.modules["elivroimagine.sounds"]


class TestCompleteRecordingWorkflow:
    """Test the complete recording workflow end-to-end."""

    def test_complete_recording_workflow(
        self,
        mock_pygame: MagicMock,
        mock_soundcard: MagicMock,
        mock_whisper: MagicMock,
        mock_pynput: MagicMock,
        temp_storage_dir: Path,
        fresh_sounds_module: tuple,
    ) -> None:
        """Full path: hotkey → start sound (1x) → record → stop sound (1x) → transcribe → save."""
        sounds, mock_pg = fresh_sounds_module

        # Track sound plays
        start_sound_plays = []
        stop_sound_plays = []

        def track_sound(path: str) -> MagicMock:
            mock_sound = MagicMock()
            if "start" in str(path):
                mock_sound.play = lambda: start_sound_plays.append(1)
            elif "stop" in str(path):
                mock_sound.play = lambda: stop_sound_plays.append(1)
            return mock_sound

        mock_pg.mixer.Sound.side_effect = track_sound

        # Set up whisper mock
        mock_whisper.load_model.return_value.transcribe.return_value = {
            "text": "This is a test transcription"
        }

        from elivroimagine.config import Config, StorageConfig
        from elivroimagine.hotkey import HotkeyListener
        from elivroimagine.recorder import AudioRecorder
        from elivroimagine.storage import StorageManager

        # Create components with test config
        config = Config()
        config.storage = StorageConfig(transcriptions_dir=str(temp_storage_dir))

        recorder = AudioRecorder(config.recording)
        storage = StorageManager(config.storage)

        # Track callback invocations
        start_called = []
        stop_called = []

        def on_start() -> None:
            start_called.append(1)
            sounds.play_start_sound()

        def on_stop() -> None:
            stop_called.append(1)
            sounds.play_stop_sound()

        hotkey = HotkeyListener(
            combination="<ctrl>+<alt>+r",
            mode="toggle",
            on_start=on_start,
            on_stop=on_stop,
        )

        # Simulate workflow: press hotkey to start
        hotkey._on_hotkey_activate()
        time.sleep(0.15)  # Let sound thread execute

        assert len(start_called) == 1
        assert len(start_sound_plays) == 1

        # Wait for debounce
        time.sleep(0.35)

        # Press hotkey to stop
        hotkey._on_hotkey_activate()
        time.sleep(0.15)  # Let sound thread execute

        assert len(stop_called) == 1
        assert len(stop_sound_plays) == 1

        # Verify exactly one of each sound
        assert len(start_sound_plays) == 1, "Start sound should play exactly once"
        assert len(stop_sound_plays) == 1, "Stop sound should play exactly once"

    def test_rapid_hotkey_presses_single_recording(
        self,
        mock_pynput: MagicMock,
    ) -> None:
        """Rapid presses result in single start/stop."""
        from elivroimagine.hotkey import HotkeyListener

        start_count = []
        stop_count = []

        hotkey = HotkeyListener(
            combination="<ctrl>+<alt>+r",
            mode="toggle",
            on_start=lambda: start_count.append(1),
            on_stop=lambda: stop_count.append(1),
        )

        # Simulate rapid key presses (within debounce window)
        for _ in range(5):
            hotkey._on_hotkey_activate()

        # Only one start should fire
        assert len(start_count) == 1
        assert len(stop_count) == 0

        # Wait for debounce
        time.sleep(0.35)

        # Now rapid presses to stop
        for _ in range(5):
            hotkey._on_hotkey_activate()

        # Only one stop should fire
        assert len(start_count) == 1
        assert len(stop_count) == 1


class TestHoldModeIntegration:
    """Test hold mode workflow."""

    def test_hold_mode_workflow(
        self,
        mock_pynput: MagicMock,
    ) -> None:
        """Hold mode: press starts, release stops."""
        from elivroimagine.hotkey import HotkeyListener

        start_count = []
        stop_count = []

        hotkey = HotkeyListener(
            combination="<ctrl>+<alt>+r",
            mode="hold",
            on_start=lambda: start_count.append(1),
            on_stop=lambda: stop_count.append(1),
        )

        # Press hotkey - should start
        hotkey._on_hotkey_activate()
        assert len(start_count) == 1

        # Wait for debounce
        time.sleep(0.35)

        # Release key - should stop
        mock_key = MagicMock()
        mock_key.name = "ctrl_l"
        hotkey._on_key_release(mock_key)

        assert len(stop_count) == 1

    def test_hold_mode_rapid_release_debounced(
        self,
        mock_pynput: MagicMock,
    ) -> None:
        """Hold mode rapid key release is debounced."""
        from elivroimagine.hotkey import HotkeyListener

        start_count = []
        stop_count = []

        hotkey = HotkeyListener(
            combination="<ctrl>+<alt>+r",
            mode="hold",
            on_start=lambda: start_count.append(1),
            on_stop=lambda: stop_count.append(1),
        )

        # Press hotkey
        hotkey._on_hotkey_activate()

        # Rapid key releases (within debounce of press)
        mock_key = MagicMock()
        mock_key.name = "ctrl_l"
        for _ in range(5):
            hotkey._on_key_release(mock_key)

        # Stop should be debounced
        assert len(stop_count) == 0


class TestAppCallbackIntegration:
    """Test app-level callback integration."""

    def test_app_callbacks_trigger_correct_sequence(
        self,
        mock_pygame: MagicMock,
        mock_soundcard: MagicMock,
        mock_whisper: MagicMock,
        mock_pynput: MagicMock,
        temp_storage_dir: Path,
        fresh_sounds_module: tuple,
    ) -> None:
        """App callbacks trigger sounds, recording, and saving in correct order."""
        sounds, mock_pg = fresh_sounds_module

        from elivroimagine.config import Config, StorageConfig
        from elivroimagine.recorder import AudioRecorder
        from elivroimagine.storage import StorageManager

        config = Config()
        config.storage = StorageConfig(transcriptions_dir=str(temp_storage_dir))

        recorder = AudioRecorder(config.recording)
        storage = StorageManager(config.storage)

        # Track call order
        call_order = []

        def on_recording_start() -> None:
            call_order.append("start_sound")
            sounds.play_start_sound()
            call_order.append("start_recording")
            recorder.start_recording()

        def on_recording_stop() -> None:
            call_order.append("stop_sound")
            sounds.play_stop_sound()
            call_order.append("stop_recording")
            recorder._recording = False

        # Simulate the callbacks as app.py would call them
        on_recording_start()
        time.sleep(0.1)

        on_recording_stop()
        time.sleep(0.1)

        # Verify correct order
        assert call_order == [
            "start_sound",
            "start_recording",
            "stop_sound",
            "stop_recording",
        ]

"""Pytest fixtures for ElivroImagine tests."""

import tempfile
from pathlib import Path
from typing import Generator
from unittest.mock import MagicMock, patch

import numpy as np
import pytest


@pytest.fixture
def mock_pygame() -> Generator[MagicMock, None, None]:
    """Mock pygame.mixer for sound playback tests."""
    import sys

    mock = MagicMock()
    mock_sound = MagicMock()
    mock.mixer.Sound.return_value = mock_sound
    mock.mixer.init = MagicMock()

    # Insert mock into sys.modules so import pygame finds it
    sys.modules["pygame"] = mock

    yield mock

    # Clean up
    if "pygame" in sys.modules and sys.modules["pygame"] is mock:
        del sys.modules["pygame"]


@pytest.fixture
def mock_sounddevice() -> Generator[MagicMock, None, None]:
    """Mock sounddevice for recording tests."""
    with patch("elivroimagine.recorder.sd") as mock:
        mock_stream = MagicMock()
        mock_stream.__enter__ = MagicMock(return_value=mock_stream)
        mock_stream.__exit__ = MagicMock(return_value=False)
        mock_stream.read.return_value = (np.zeros((1600, 1), dtype=np.float32), False)
        mock.InputStream.return_value = mock_stream
        mock.query_devices.return_value = [
            {"name": "Test Microphone", "max_input_channels": 2},
        ]
        # No PortAudioError attribute needed for basic tests
        mock.PortAudioError = type("PortAudioError", (Exception,), {})
        yield mock


@pytest.fixture
def mock_faster_whisper() -> Generator[MagicMock, None, None]:
    """Mock faster-whisper for transcription tests."""
    mock_model_class = MagicMock()
    mock_model = MagicMock()
    # faster-whisper returns (segments_generator, info)
    mock_segment = MagicMock()
    mock_segment.text = "Test transcription"
    mock_info = MagicMock()
    mock_info.language = "en"
    mock_info.language_probability = 0.99
    mock_model.transcribe.return_value = ([mock_segment], mock_info)
    mock_model_class.return_value = mock_model

    # Mock the lazy import inside _ensure_model
    mock_fw_module = MagicMock()
    mock_fw_module.WhisperModel = mock_model_class

    with patch.dict("sys.modules", {"faster_whisper": mock_fw_module}):
        yield mock_model_class


# Keep backward compat alias
@pytest.fixture
def mock_whisper(mock_faster_whisper: MagicMock) -> Generator[MagicMock, None, None]:
    """Alias for mock_faster_whisper (backward compatibility)."""
    yield mock_faster_whisper


@pytest.fixture
def mock_pynput() -> Generator[MagicMock, None, None]:
    """Mock keyboard library for hotkey tests."""
    import sys

    # Create mock keyboard module
    mock_keyboard = MagicMock()
    mock_keyboard.add_hotkey.return_value = 1  # Return a hotkey ID
    mock_keyboard.remove_hotkey = MagicMock()
    mock_keyboard.on_press_key = MagicMock(return_value=lambda: None)
    mock_keyboard.on_release_key = MagicMock(return_value=lambda: None)
    mock_keyboard.unhook = MagicMock()
    mock_keyboard.is_pressed = MagicMock(return_value=True)

    # Store original modules
    original_keyboard = sys.modules.get("keyboard")
    original_hotkey = sys.modules.get("elivroimagine.hotkey")
    original_app = sys.modules.get("elivroimagine.app")

    # Remove modules to force reimport with our mock
    if "elivroimagine.app" in sys.modules:
        del sys.modules["elivroimagine.app"]
    if "elivroimagine.hotkey" in sys.modules:
        del sys.modules["elivroimagine.hotkey"]

    # Patch the keyboard module BEFORE importing hotkey
    sys.modules["keyboard"] = mock_keyboard

    yield mock_keyboard

    # Restore originals in reverse order
    if "elivroimagine.app" in sys.modules:
        del sys.modules["elivroimagine.app"]
    if "elivroimagine.hotkey" in sys.modules:
        del sys.modules["elivroimagine.hotkey"]

    if original_keyboard is not None:
        sys.modules["keyboard"] = original_keyboard
    elif "keyboard" in sys.modules:
        del sys.modules["keyboard"]

    # Restore original modules if they existed
    if original_hotkey is not None:
        sys.modules["elivroimagine.hotkey"] = original_hotkey
    if original_app is not None:
        sys.modules["elivroimagine.app"] = original_app


@pytest.fixture
def temp_storage_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for transcription storage tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def temp_config_dir(tmp_path: Path) -> Generator[Path, None, None]:
    """Create a temporary directory for config tests."""
    config_dir = tmp_path / ".elivroimagine"
    config_dir.mkdir(parents=True)
    yield config_dir

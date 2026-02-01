"""Pytest fixtures for ElivroImagine tests."""

import tempfile
from pathlib import Path
from typing import Generator
from unittest.mock import MagicMock, patch

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
def mock_soundcard() -> Generator[MagicMock, None, None]:
    """Mock soundcard for recording tests."""
    with patch("elivroimagine.recorder.sc") as mock:
        mock_mic = MagicMock()
        mock_recorder = MagicMock()
        mock_recorder.__enter__ = MagicMock(return_value=mock_recorder)
        mock_recorder.__exit__ = MagicMock(return_value=False)
        mock_mic.recorder.return_value = mock_recorder
        mock.default_microphone.return_value = mock_mic
        yield mock


@pytest.fixture
def mock_whisper() -> Generator[MagicMock, None, None]:
    """Mock whisper for transcription tests."""
    with patch("elivroimagine.transcriber.whisper") as mock:
        mock_model = MagicMock()
        mock_model.transcribe.return_value = {"text": "Test transcription"}
        mock.load_model.return_value = mock_model
        yield mock


@pytest.fixture
def mock_pynput() -> Generator[MagicMock, None, None]:
    """Mock pynput.keyboard for hotkey tests."""
    with patch("elivroimagine.hotkey.keyboard") as mock:
        mock_listener = MagicMock()
        mock_listener.start = MagicMock()
        mock_listener.stop = MagicMock()
        mock.GlobalHotKeys.return_value = mock_listener
        mock.Listener.return_value = mock_listener
        yield mock


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

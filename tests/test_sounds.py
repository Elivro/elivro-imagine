"""Tests for sound playback functionality."""

import importlib
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

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


class TestSoundPlayback:
    """Test sound playback functions."""

    def test_play_start_sound_plays_once(
        self, fresh_sounds_module: tuple
    ) -> None:
        """Start sound plays exactly once per call."""
        sounds, mock_pygame = fresh_sounds_module

        sounds.play_start_sound()

        # Give thread time to execute
        time.sleep(0.15)

        # Verify Sound was created and played once
        mock_pygame.mixer.Sound.assert_called_once()
        mock_pygame.mixer.Sound.return_value.play.assert_called_once()

    def test_play_stop_sound_plays_once(
        self, fresh_sounds_module: tuple
    ) -> None:
        """Stop sound plays exactly once per call."""
        sounds, mock_pygame = fresh_sounds_module

        sounds.play_stop_sound()

        # Give thread time to execute
        time.sleep(0.15)

        mock_pygame.mixer.Sound.assert_called_once()
        mock_pygame.mixer.Sound.return_value.play.assert_called_once()

    def test_start_sound_volume_is_applied(
        self, fresh_sounds_module: tuple
    ) -> None:
        """Start sound has correct volume applied."""
        sounds, mock_pygame = fresh_sounds_module

        sounds.play_start_sound()  # Uses default volume 1.0
        time.sleep(0.15)

        mock_sound = mock_pygame.mixer.Sound.return_value
        mock_sound.set_volume.assert_called_once_with(1.0)

    def test_stop_sound_volume_is_applied(
        self, fresh_sounds_module: tuple
    ) -> None:
        """Stop sound has correct volume applied."""
        sounds, mock_pygame = fresh_sounds_module

        sounds.play_stop_sound()  # Uses default volume 0.7
        time.sleep(0.15)

        mock_sound = mock_pygame.mixer.Sound.return_value
        mock_sound.set_volume.assert_called_once_with(0.7)

    def test_custom_volume_is_applied(
        self, fresh_sounds_module: tuple
    ) -> None:
        """Custom volume parameter is applied correctly."""
        sounds, mock_pygame = fresh_sounds_module

        sounds.play_start_sound(volume=0.5)
        time.sleep(0.15)

        mock_sound = mock_pygame.mixer.Sound.return_value
        mock_sound.set_volume.assert_called_once_with(0.5)

    def test_multiple_plays_each_trigger_once(
        self, fresh_sounds_module: tuple
    ) -> None:
        """Multiple calls each trigger a single play."""
        sounds, mock_pygame = fresh_sounds_module

        sounds.play_start_sound()
        time.sleep(0.15)

        sounds.play_stop_sound()
        time.sleep(0.15)

        # Each sound played once
        assert mock_pygame.mixer.Sound.return_value.play.call_count == 2


class TestMixerInitialization:
    """Test mixer initialization behavior."""

    def test_mixer_initializes_once(self, fresh_sounds_module: tuple) -> None:
        """Mixer only initializes once across multiple plays."""
        sounds, mock_pygame = fresh_sounds_module

        sounds.play_start_sound()
        time.sleep(0.15)
        sounds.play_start_sound()
        time.sleep(0.15)
        sounds.play_stop_sound()
        time.sleep(0.15)

        # Mixer should only be initialized once
        mock_pygame.mixer.init.assert_called_once()

    def test_handles_missing_sound_file(
        self, fresh_sounds_module: tuple
    ) -> None:
        """Gracefully handles missing sound file."""
        sounds, mock_pygame = fresh_sounds_module

        # Override the path to a nonexistent file
        original_path = sounds.START_SOUND
        sounds.START_SOUND = Path("/nonexistent/file.mp3")

        try:
            # Should not raise, just log warning
            sounds.play_start_sound()
            time.sleep(0.15)

            # Sound should not be created for nonexistent file
            mock_pygame.mixer.Sound.assert_not_called()
        finally:
            sounds.START_SOUND = original_path

    def test_handles_mixer_init_failure(self, mock_pygame: MagicMock) -> None:
        """Gracefully handles mixer initialization failure."""
        mock_pygame.mixer.init.side_effect = Exception("No audio device")

        # Remove cached module
        if "elivroimagine.sounds" in sys.modules:
            del sys.modules["elivroimagine.sounds"]

        import elivroimagine.sounds

        elivroimagine.sounds._mixer_initialized = False

        # Should not raise
        elivroimagine.sounds.play_start_sound()
        time.sleep(0.15)

        # Clean up
        del sys.modules["elivroimagine.sounds"]

"""Tests for system tray functionality."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestTrayIconState:
    """Test tray icon state changes."""

    def test_set_recording_true_changes_icon(self) -> None:
        """Setting recording true changes icon to recording state."""
        with patch("elivroimagine.tray.Icon"):
            from elivroimagine.tray import SystemTray

            tray = SystemTray(
                on_settings=MagicMock(),
                on_quit=MagicMock(),
                transcriptions_folder=Path("/tmp/transcriptions"),
            )
            tray._icon = MagicMock()

            tray.set_recording(True)

            assert tray._recording is True
            assert tray._icon.icon == tray._icon_recording
            assert "Recording" in tray._icon.title

    def test_set_recording_false_changes_icon(self) -> None:
        """Setting recording false changes icon to idle state."""
        with patch("elivroimagine.tray.Icon"):
            from elivroimagine.tray import SystemTray

            tray = SystemTray(
                on_settings=MagicMock(),
                on_quit=MagicMock(),
                transcriptions_folder=Path("/tmp/transcriptions"),
            )
            tray._icon = MagicMock()
            tray._recording = True

            tray.set_recording(False)

            assert tray._recording is False
            assert tray._icon.icon == tray._icon_idle
            assert "Ready" in tray._icon.title

    def test_set_recording_no_icon_does_not_crash(self) -> None:
        """Setting recording when icon is None doesn't crash."""
        with patch("elivroimagine.tray.Icon"):
            from elivroimagine.tray import SystemTray

            tray = SystemTray(
                on_settings=MagicMock(),
                on_quit=MagicMock(),
                transcriptions_folder=Path("/tmp/transcriptions"),
            )
            tray._icon = None

            # Should not raise
            tray.set_recording(True)
            tray.set_recording(False)


class TestTrayTranscribingState:
    """Test tray transcribing state changes."""

    def test_set_transcribing_true_changes_icon(self) -> None:
        """Setting transcribing true changes icon to transcribing state."""
        with patch("elivroimagine.tray.Icon"):
            from elivroimagine.tray import SystemTray

            tray = SystemTray(
                on_settings=MagicMock(),
                on_quit=MagicMock(),
                transcriptions_folder=Path("/tmp/transcriptions"),
            )
            tray._icon = MagicMock()

            tray.set_transcribing(True)

            assert tray._transcribing is True
            assert tray._icon.icon == tray._icon_transcribing
            assert "Transcribing" in tray._icon.title

    def test_set_transcribing_false_returns_to_idle(self) -> None:
        """Setting transcribing false returns to idle state."""
        with patch("elivroimagine.tray.Icon"):
            from elivroimagine.tray import SystemTray

            tray = SystemTray(
                on_settings=MagicMock(),
                on_quit=MagicMock(),
                transcriptions_folder=Path("/tmp/transcriptions"),
            )
            tray._icon = MagicMock()
            tray._transcribing = True

            tray.set_transcribing(False)

            assert tray._transcribing is False
            assert tray._icon.icon == tray._icon_idle
            assert "Ready" in tray._icon.title

    def test_recording_takes_priority_over_transcribing(self) -> None:
        """Recording state takes priority over transcribing state."""
        with patch("elivroimagine.tray.Icon"):
            from elivroimagine.tray import SystemTray

            tray = SystemTray(
                on_settings=MagicMock(),
                on_quit=MagicMock(),
                transcriptions_folder=Path("/tmp/transcriptions"),
            )
            tray._icon = MagicMock()

            # Set transcribing first
            tray.set_transcribing(True)
            # Then start recording
            tray.set_recording(True)

            # Icon should show recording, not transcribing
            assert tray._icon.icon == tray._icon_recording

    def test_transcribing_shown_after_recording_stops(self) -> None:
        """Transcribing state shown when recording stops but transcription ongoing."""
        with patch("elivroimagine.tray.Icon"):
            from elivroimagine.tray import SystemTray

            tray = SystemTray(
                on_settings=MagicMock(),
                on_quit=MagicMock(),
                transcriptions_folder=Path("/tmp/transcriptions"),
            )
            tray._icon = MagicMock()

            # Start transcribing, then start and stop recording
            tray.set_transcribing(True)
            tray.set_recording(True)
            tray.set_recording(False)

            # Should show transcribing state since transcription still in progress
            assert tray._icon.icon == tray._icon_transcribing
            assert "Transcribing" in tray._icon.title


class TestTrayFolderOperations:
    """Test tray folder operations."""

    def test_open_folder_creates_if_missing(self, tmp_path: Path) -> None:
        """Opening folder creates it if it doesn't exist."""
        with patch("elivroimagine.tray.Icon"):
            from elivroimagine.tray import SystemTray

            folder = tmp_path / "transcriptions"
            assert not folder.exists()

            tray = SystemTray(
                on_settings=MagicMock(),
                on_quit=MagicMock(),
                transcriptions_folder=folder,
            )

            with patch("subprocess.Popen"):
                tray._open_transcriptions_folder()

            assert folder.exists()

    def test_open_folder_handles_creation_error(self, tmp_path: Path) -> None:
        """Opening folder handles creation error gracefully."""
        with patch("elivroimagine.tray.Icon"):
            from elivroimagine.tray import SystemTray

            # Use a path that can't be created (file as parent)
            file_path = tmp_path / "file.txt"
            file_path.write_text("content")
            folder = file_path / "subfolder"

            tray = SystemTray(
                on_settings=MagicMock(),
                on_quit=MagicMock(),
                transcriptions_folder=folder,
            )

            with patch("subprocess.Popen") as mock_popen:
                # Should not raise, and should not open
                tray._open_transcriptions_folder()
                mock_popen.assert_not_called()

    def test_open_folder_handles_open_error(self, tmp_path: Path) -> None:
        """Opening folder handles subprocess error gracefully."""
        with patch("elivroimagine.tray.Icon"):
            from elivroimagine.tray import SystemTray

            folder = tmp_path / "transcriptions"
            folder.mkdir()

            tray = SystemTray(
                on_settings=MagicMock(),
                on_quit=MagicMock(),
                transcriptions_folder=folder,
            )

            with patch("subprocess.Popen", side_effect=OSError("Failed")):
                # Should not raise
                tray._open_transcriptions_folder()


class TestTrayNotifications:
    """Test tray notification functionality."""

    def test_notify_sends_notification(self) -> None:
        """Notify sends notification through icon."""
        with patch("elivroimagine.tray.Icon"):
            from elivroimagine.tray import SystemTray

            tray = SystemTray(
                on_settings=MagicMock(),
                on_quit=MagicMock(),
                transcriptions_folder=Path("/tmp/transcriptions"),
            )
            tray._icon = MagicMock()

            tray.notify("Test Title", "Test Message")

            tray._icon.notify.assert_called_once_with("Test Message", "Test Title")

    def test_notify_no_icon_does_not_crash(self) -> None:
        """Notify when icon is None doesn't crash."""
        with patch("elivroimagine.tray.Icon"):
            from elivroimagine.tray import SystemTray

            tray = SystemTray(
                on_settings=MagicMock(),
                on_quit=MagicMock(),
                transcriptions_folder=Path("/tmp/transcriptions"),
            )
            tray._icon = None

            # Should not raise
            tray.notify("Test", "Test")


class TestTrayLifecycle:
    """Test tray start/stop lifecycle."""

    def test_stop_stops_icon(self) -> None:
        """Stop properly stops the icon."""
        with patch("elivroimagine.tray.Icon"):
            from elivroimagine.tray import SystemTray

            tray = SystemTray(
                on_settings=MagicMock(),
                on_quit=MagicMock(),
                transcriptions_folder=Path("/tmp/transcriptions"),
            )
            mock_icon = MagicMock()
            tray._icon = mock_icon

            tray.stop()

            mock_icon.stop.assert_called_once()
            assert tray._icon is None

    def test_stop_no_icon_does_not_crash(self) -> None:
        """Stop when icon is None doesn't crash."""
        with patch("elivroimagine.tray.Icon"):
            from elivroimagine.tray import SystemTray

            tray = SystemTray(
                on_settings=MagicMock(),
                on_quit=MagicMock(),
                transcriptions_folder=Path("/tmp/transcriptions"),
            )
            tray._icon = None

            # Should not raise
            tray.stop()

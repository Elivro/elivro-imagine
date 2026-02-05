"""Tests for main application orchestrator."""

import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest


def _create_app(tmp_path: Path) -> "ElivroImagineApp":
    """Helper to create app with all components mocked."""
    with patch("elivroimagine.app.Config") as mock_config_class:
        mock_config = MagicMock()
        mock_config.recording = MagicMock()
        mock_config.whisper = MagicMock()
        mock_config.storage = MagicMock()
        mock_config.storage.transcriptions_path = tmp_path / "transcriptions"
        mock_config.hotkey = MagicMock()
        mock_config.hotkey.combination = "<ctrl>+<alt>+r"
        mock_config.hotkey.mode = "hold"
        mock_config.paste_hotkey = MagicMock()
        mock_config.paste_hotkey.enabled = False
        mock_config.devtracker = MagicMock()
        mock_config.devtracker.enabled = False
        mock_config.devtracker_hotkey = MagicMock()
        mock_config.devtracker_hotkey.enabled = False
        mock_config.sound = MagicMock()
        mock_config.get_config_dir.return_value = tmp_path
        mock_config_class.load.return_value = mock_config
        mock_config_class.get_config_path.return_value = tmp_path / "config.yaml"

        with patch("elivroimagine.app.SingleInstanceLock") as mock_lock_class:
            mock_lock = MagicMock()
            mock_lock.acquire.return_value = True
            mock_lock_class.return_value = mock_lock

            with patch("elivroimagine.app.AudioRecorder"):
                with patch("elivroimagine.app.Transcriber"):
                    with patch("elivroimagine.app.StorageManager"):
                        with patch("elivroimagine.app.HotkeyListener"):
                            with patch("elivroimagine.app.SystemTray"):
                                from elivroimagine.app import ElivroImagineApp

                                return ElivroImagineApp()


class TestAppInitialization:
    """Test application initialization."""

    def test_app_initializes_all_components(self, tmp_path: Path) -> None:
        """App initializes all required components."""
        app = _create_app(tmp_path)

        assert app.recorder is not None
        assert app.transcriber is not None
        assert app.storage is not None
        assert app.hotkey is not None
        assert app.tray is not None

    def test_app_config_is_directly_accessible(self, tmp_path: Path) -> None:
        """App config uses atomic reference read (GIL provides safety)."""
        app = _create_app(tmp_path)
        assert hasattr(app, "config")

    def test_app_acquires_instance_lock(self, tmp_path: Path) -> None:
        """App acquires single instance lock on init."""
        app = _create_app(tmp_path)
        assert app._instance_lock is not None

    def test_component_init_failure_returns_none(self, tmp_path: Path) -> None:
        """Failed component initialization returns None instead of crashing."""
        with patch("elivroimagine.app.Config") as mock_config_class:
            mock_config = MagicMock()
            mock_config.recording = MagicMock()
            mock_config.whisper = MagicMock()
            mock_config.storage = MagicMock()
            mock_config.storage.transcriptions_path = tmp_path / "transcriptions"
            mock_config.hotkey = MagicMock()
            mock_config.hotkey.combination = "<ctrl>+<alt>+r"
            mock_config.hotkey.mode = "hold"
            mock_config.paste_hotkey = MagicMock()
            mock_config.paste_hotkey.enabled = False
            mock_config.devtracker = MagicMock()
            mock_config.devtracker.enabled = False
            mock_config.devtracker_hotkey = MagicMock()
            mock_config.devtracker_hotkey.enabled = False
            mock_config.sound = MagicMock()
            mock_config.get_config_dir.return_value = tmp_path
            mock_config_class.load.return_value = mock_config
            mock_config_class.get_config_path.return_value = tmp_path / "config.yaml"

            with patch("elivroimagine.app.SingleInstanceLock") as mock_lock_class:
                mock_lock = MagicMock()
                mock_lock.acquire.return_value = True
                mock_lock_class.return_value = mock_lock

                with patch(
                    "elivroimagine.app.AudioRecorder",
                    side_effect=RuntimeError("No mic"),
                ):
                    with patch("elivroimagine.app.Transcriber"):
                        with patch("elivroimagine.app.StorageManager"):
                            with patch("elivroimagine.app.HotkeyListener"):
                                with patch("elivroimagine.app.SystemTray"):
                                    from elivroimagine.app import ElivroImagineApp

                                    app = ElivroImagineApp()

                                    # Recorder should be None (failed to init)
                                    assert app.recorder is None
                                    # Other components should still work
                                    assert app.transcriber is not None


class TestAppRecordingCallbacks:
    """Test application recording callbacks."""

    def test_on_recording_start_plays_sound(self, tmp_path: Path) -> None:
        """Recording start plays sound when enabled."""
        with patch("elivroimagine.app.play_start_sound") as mock_play:
            app = _create_app(tmp_path)
            app.config.sound.enabled = True
            app.config.sound.start_volume = 0.8
            app._on_save_recording_start()

            mock_play.assert_called_once_with(0.8)

    def test_on_recording_stop_plays_sound(self, tmp_path: Path) -> None:
        """Recording stop plays sound when enabled."""
        with patch("elivroimagine.app.play_stop_sound") as mock_play:
            app = _create_app(tmp_path)
            app.config.sound.enabled = True
            app.config.sound.stop_volume = 0.7
            app.recorder.stop_recording.return_value = None
            # Must start recording first to own it
            app._do_recording_start("save")
            app._on_save_recording_stop()

            mock_play.assert_called_once_with(0.7)

    def test_on_recording_start_without_recorder(self, tmp_path: Path) -> None:
        """Recording start with unavailable recorder shows notification."""
        app = _create_app(tmp_path)
        app.recorder = None

        # Should not raise
        app._on_save_recording_start()
        app.tray.notify.assert_called()


class TestAppShutdown:
    """Test application shutdown."""

    def test_quit_stops_all_components(self, tmp_path: Path) -> None:
        """Quit stops all components properly."""
        with patch("elivroimagine.sounds.cleanup_mixer"):
            app = _create_app(tmp_path)
            app.recorder.is_recording = False
            app._quit()

            app.hotkey.stop.assert_called_once()
            app.tray.stop.assert_called_once()
            assert app._running is False

    def test_quit_stops_active_recording(self, tmp_path: Path) -> None:
        """Quit stops recording if active."""
        with patch("elivroimagine.sounds.cleanup_mixer"):
            app = _create_app(tmp_path)
            app.recorder.is_recording = True
            app._quit()

            app.recorder.stop_recording.assert_called_once()

    def test_quit_releases_instance_lock(self, tmp_path: Path) -> None:
        """Quit releases the single instance lock."""
        with patch("elivroimagine.sounds.cleanup_mixer"):
            app = _create_app(tmp_path)
            app.recorder.is_recording = False
            app._quit()

            app._instance_lock.release.assert_called_once()

    def test_quit_shuts_down_thread_pool(self, tmp_path: Path) -> None:
        """Quit shuts down the transcription thread pool."""
        with patch("elivroimagine.sounds.cleanup_mixer"):
            app = _create_app(tmp_path)
            app.recorder.is_recording = False

            # Mock the thread pool
            mock_pool = MagicMock()
            app._transcription_pool = mock_pool

            app._quit()

            mock_pool.shutdown.assert_called_once()


class TestRecordingConflictGuard:
    """Test recording ownership and conflict prevention."""

    def test_save_blocks_paste(self, tmp_path: Path) -> None:
        """Starting save recording blocks paste recording."""
        app = _create_app(tmp_path)

        assert app._do_recording_start("save") is True
        assert app._do_recording_start("paste") is False
        assert app._active_recording_source == "save"

    def test_paste_blocks_save(self, tmp_path: Path) -> None:
        """Starting paste recording blocks save recording."""
        app = _create_app(tmp_path)

        assert app._do_recording_start("paste") is True
        assert app._do_recording_start("save") is False
        assert app._active_recording_source == "paste"

    def test_stop_wrong_source_ignored(self, tmp_path: Path) -> None:
        """Stopping recording from wrong source is ignored."""
        with patch("elivroimagine.app.play_start_sound"):
            app = _create_app(tmp_path)
            app.config.sound.enabled = False

            app._do_recording_start("save")
            result = app._do_recording_stop("paste")

            assert result is None
            assert app._active_recording_source == "save"

    def test_stop_correct_source_succeeds(self, tmp_path: Path) -> None:
        """Stopping recording from correct source clears ownership."""
        with patch("elivroimagine.app.play_stop_sound"):
            app = _create_app(tmp_path)
            app.config.sound.enabled = False
            audio = np.zeros(16000, dtype=np.float32)
            app.recorder.stop_recording.return_value = (audio, 1.0)

            app._do_recording_start("save")
            result = app._do_recording_stop("save")

            assert result is not None
            assert app._active_recording_source is None

    def test_recording_freed_after_stop(self, tmp_path: Path) -> None:
        """After stopping, the other source can start recording."""
        with patch("elivroimagine.app.play_stop_sound"):
            app = _create_app(tmp_path)
            app.config.sound.enabled = False
            app.recorder.stop_recording.return_value = None

            app._do_recording_start("save")
            app._do_recording_stop("save")

            assert app._do_recording_start("paste") is True

    def test_hotkey_capture_blocks_recording(self, tmp_path: Path) -> None:
        """Recording is blocked when hotkey capture is active in settings."""
        app = _create_app(tmp_path)

        # Simulate hotkey capture active in settings window
        app._hotkey_capture_active = True

        # Both save and paste should be blocked
        assert app._do_recording_start("save") is False
        assert app._do_recording_start("paste") is False
        assert app._active_recording_source is None

        # Recording should work when capture ends
        app._hotkey_capture_active = False
        assert app._do_recording_start("save") is True


class TestTranscribeAndPaste:
    """Test _transcribe_and_paste method."""

    def test_transcribe_and_paste_calls_paster(self, tmp_path: Path) -> None:
        """Transcribe and paste calls paster.paste_text with transcribed text."""
        app = _create_app(tmp_path)
        app.paster = MagicMock()
        app.paster.paste_text.return_value = True

        audio = np.zeros(16000, dtype=np.float32)
        app.transcriber.transcribe.return_value = "Hello world"

        app._transcribe_and_paste(audio, 1.0)

        app.paster.paste_text.assert_called_once_with("Hello world")
        # notify is NOT called on success (only on errors)

    def test_transcribe_and_paste_empty_text(self, tmp_path: Path) -> None:
        """Transcribe and paste with empty text shows notification."""
        app = _create_app(tmp_path)
        app.paster = MagicMock()

        audio = np.zeros(16000, dtype=np.float32)
        app.transcriber.transcribe.return_value = "   "

        app._transcribe_and_paste(audio, 1.0)

        app.paster.paste_text.assert_not_called()

    def test_transcribe_and_paste_no_paster(self, tmp_path: Path) -> None:
        """Transcribe and paste with no paster shows error."""
        app = _create_app(tmp_path)
        app.paster = None

        audio = np.zeros(16000, dtype=np.float32)

        app._transcribe_and_paste(audio, 1.0)

        app.tray.notify.assert_called()

    def test_transcribe_and_paste_failure(self, tmp_path: Path) -> None:
        """Paste failure shows error notification."""
        app = _create_app(tmp_path)
        app.paster = MagicMock()
        app.paster.paste_text.return_value = False

        audio = np.zeros(16000, dtype=np.float32)
        app.transcriber.transcribe.return_value = "Hello"

        app._transcribe_and_paste(audio, 1.0)

        # Should notify about paste failure
        error_calls = [
            c for c in app.tray.notify.call_args_list
            if "Failed" in str(c) or "Error" in str(c)
        ]
        assert len(error_calls) > 0


class TestDevTrackerHotkeyConflicts:
    """Test recording conflicts involving the devtracker hotkey."""

    def test_devtracker_blocks_save(self, tmp_path: Path) -> None:
        """Starting devtracker recording blocks save recording."""
        app = _create_app(tmp_path)

        assert app._do_recording_start("devtracker") is True
        assert app._do_recording_start("save") is False
        assert app._active_recording_source == "devtracker"

    def test_devtracker_blocks_paste(self, tmp_path: Path) -> None:
        """Starting devtracker recording blocks paste recording."""
        app = _create_app(tmp_path)

        assert app._do_recording_start("devtracker") is True
        assert app._do_recording_start("paste") is False
        assert app._active_recording_source == "devtracker"

    def test_save_blocks_devtracker(self, tmp_path: Path) -> None:
        """Starting save recording blocks devtracker recording."""
        app = _create_app(tmp_path)

        assert app._do_recording_start("save") is True
        assert app._do_recording_start("devtracker") is False
        assert app._active_recording_source == "save"

    def test_paste_blocks_devtracker(self, tmp_path: Path) -> None:
        """Starting paste recording blocks devtracker recording."""
        app = _create_app(tmp_path)

        assert app._do_recording_start("paste") is True
        assert app._do_recording_start("devtracker") is False
        assert app._active_recording_source == "paste"

    def test_devtracker_stop_wrong_source_ignored(self, tmp_path: Path) -> None:
        """Stopping devtracker recording from wrong source is ignored."""
        with patch("elivroimagine.app.play_start_sound"):
            app = _create_app(tmp_path)
            app.config.sound.enabled = False

            app._do_recording_start("devtracker")
            result = app._do_recording_stop("save")

            assert result is None
            assert app._active_recording_source == "devtracker"

    def test_devtracker_stop_correct_source_succeeds(self, tmp_path: Path) -> None:
        """Stopping recording from devtracker source clears ownership."""
        with patch("elivroimagine.app.play_stop_sound"):
            app = _create_app(tmp_path)
            app.config.sound.enabled = False
            audio = np.zeros(16000, dtype=np.float32)
            app.recorder.stop_recording.return_value = (audio, 1.0)

            app._do_recording_start("devtracker")
            result = app._do_recording_stop("devtracker")

            assert result is not None
            assert app._active_recording_source is None

    def test_hotkey_capture_blocks_devtracker(self, tmp_path: Path) -> None:
        """Devtracker recording is blocked when hotkey capture is active."""
        app = _create_app(tmp_path)
        app._hotkey_capture_active = True

        assert app._do_recording_start("devtracker") is False
        assert app._active_recording_source is None


class TestDevTrackerProjectOverride:
    """Test task creation with project override."""

    def test_create_task_with_project_override(self, tmp_path: Path) -> None:
        """_create_devtracker_task passes project_override to client."""
        app = _create_app(tmp_path)
        app._devtracker = MagicMock()
        app._devtracker.get_active_and_backlog_tasks.return_value = []
        app._devtracker.get_category_id.return_value = 1
        app._devtracker.create_task.return_value = {"id": 42, "title": "Test"}

        with patch("elivroimagine.app.classify_transcription") as mock_classify:
            mock_result = MagicMock()
            mock_result.title = "Test Task"
            mock_result.description = "Description"
            mock_result.category = "feature"
            mock_result.priority = "medium"
            mock_result.effort = "medium"
            mock_classify.return_value = mock_result

            app._create_devtracker_task("some text", project_override="intranet")

            app._devtracker.create_task.assert_called_once()
            call_kwargs = app._devtracker.create_task.call_args
            assert call_kwargs.kwargs.get("project_override") == "intranet"

    def test_create_task_without_override_uses_default(self, tmp_path: Path) -> None:
        """_create_devtracker_task without override passes None."""
        app = _create_app(tmp_path)
        app._devtracker = MagicMock()
        app._devtracker.get_active_and_backlog_tasks.return_value = []
        app._devtracker.get_category_id.return_value = 1
        app._devtracker.create_task.return_value = {"id": 43, "title": "Test"}

        with patch("elivroimagine.app.classify_transcription") as mock_classify:
            mock_result = MagicMock()
            mock_result.title = "Test Task"
            mock_result.description = "Description"
            mock_result.category = "feature"
            mock_result.priority = "medium"
            mock_result.effort = "medium"
            mock_classify.return_value = mock_result

            app._create_devtracker_task("some text")

            call_kwargs = app._devtracker.create_task.call_args
            assert call_kwargs.kwargs.get("project_override") is None

    def test_notification_includes_project_name(self, tmp_path: Path) -> None:
        """Task created notification includes project name."""
        app = _create_app(tmp_path)
        app._devtracker = MagicMock()
        app._devtracker.get_active_and_backlog_tasks.return_value = []
        app._devtracker.get_category_id.return_value = 1
        app._devtracker.create_task.return_value = {"id": 99, "title": "Test"}

        with patch("elivroimagine.app.classify_transcription") as mock_classify:
            mock_result = MagicMock()
            mock_result.title = "Test Task"
            mock_result.description = "Description"
            mock_result.category = "feature"
            mock_result.priority = "medium"
            mock_result.effort = "medium"
            mock_classify.return_value = mock_result

            app._create_devtracker_task("some text", project_override="intranet")

            # Check notification title includes project name
            notify_calls = app.tray.notify.call_args_list
            task_created_calls = [
                c for c in notify_calls if "intranet" in str(c)
            ]
            assert len(task_created_calls) > 0

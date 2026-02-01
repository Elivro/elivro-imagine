"""Main application orchestrator for ElivroImagine."""

import logging
import sys
import threading
from pathlib import Path

from .config import Config
from .hotkey import HotkeyListener
from .recorder import AudioRecorder
from .settings_ui import SettingsWindow
from .sounds import play_start_sound, play_stop_sound
from .storage import StorageManager
from .transcriber import Transcriber
from .tray import SystemTray

logger = logging.getLogger(__name__)


class ElivroImagineApp:
    """Main application class that orchestrates all components."""

    def __init__(self) -> None:
        """Initialize the application."""
        self.config = Config.load()
        self.config.ensure_directories()
        self._setup_logging()

        logger.info("Initializing ElivroImagine")

        # Initialize components
        self.recorder = AudioRecorder(self.config.recording)
        self.transcriber = Transcriber(self.config.whisper)
        self.storage = StorageManager(self.config.storage)

        # Set up hotkey listener
        self.hotkey = HotkeyListener(
            combination=self.config.hotkey.combination,
            mode=self.config.hotkey.mode,
            on_start=self._on_recording_start,
            on_stop=self._on_recording_stop,
        )

        # Set up system tray
        self.tray = SystemTray(
            on_settings=self._show_settings,
            on_quit=self._quit,
            transcriptions_folder=self.storage.get_transcriptions_folder(),
        )

        # Set up recorder status callback
        self.recorder.set_status_callback(self._on_recorder_status)

        self._running = False
        self._settings_thread: threading.Thread | None = None

    def _setup_logging(self) -> None:
        """Set up logging configuration."""
        log_dir = self.config.get_config_dir() / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "elivroimagine.log"

        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=[
                logging.FileHandler(log_file, encoding="utf-8"),
                logging.StreamHandler(sys.stdout),
            ],
        )

    def run(self) -> None:
        """Run the application."""
        logger.info("Starting ElivroImagine")
        self._running = True

        # Pre-load Whisper model in background
        threading.Thread(target=self._preload_model, daemon=True).start()

        # Start components
        self.hotkey.start()
        self.tray.start()

        logger.info(
            f"ElivroImagine running. Hotkey: {self.config.hotkey.combination} "
            f"(mode: {self.config.hotkey.mode})"
        )

        # Keep main thread alive
        try:
            while self._running:
                threading.Event().wait(1)
        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt")
            self._quit()

    def _preload_model(self) -> None:
        """Pre-load Whisper model in background."""
        logger.info("Pre-loading Whisper model...")
        try:
            self.transcriber._ensure_model()
            logger.info("Whisper model ready")
        except Exception as e:
            logger.error(f"Failed to pre-load Whisper model: {e}")

    def _on_recording_start(self) -> None:
        """Handle recording start."""
        logger.info("Recording started")
        play_start_sound()
        self.tray.set_recording(True)
        self.recorder.start_recording()

    def _on_recording_stop(self) -> None:
        """Handle recording stop."""
        logger.info("Recording stopped")
        play_stop_sound()
        self.tray.set_recording(False)

        result = self.recorder.stop_recording()
        if result is None:
            logger.warning("No audio recorded")
            self.tray.notify("ElivroImagine", "No audio recorded")
            return

        audio, duration = result

        if duration < 0.5:
            logger.warning("Recording too short")
            self.tray.notify("ElivroImagine", "Recording too short (< 0.5s)")
            return

        # Transcribe in background
        threading.Thread(
            target=self._transcribe_and_save,
            args=(audio, duration),
            daemon=True,
        ).start()

    def _transcribe_and_save(self, audio, duration: float) -> None:
        """Transcribe audio and save to file."""
        try:
            logger.info(f"Transcribing {duration:.1f}s of audio...")

            text = self.transcriber.transcribe(audio, self.config.recording.sample_rate)

            if not text.strip():
                logger.warning("Transcription returned empty text")
                self.tray.notify("ElivroImagine", "No speech detected")
                return

            filepath = self.storage.save_transcription(text, duration)
            logger.info(f"Saved transcription to {filepath}")

            # Show preview in notification
            preview = text[:100] + "..." if len(text) > 100 else text
            self.tray.notify("Transcription Saved", preview)

        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            self.tray.notify("ElivroImagine Error", f"Transcription failed: {e}")

    def _on_recorder_status(self, status: str) -> None:
        """Handle recorder status changes."""
        logger.debug(f"Recorder status: {status}")
        if status.startswith("error:"):
            self.tray.notify("ElivroImagine Error", status)

    def _show_settings(self) -> None:
        """Show settings window."""
        if self._settings_thread and self._settings_thread.is_alive():
            return

        def run_settings():
            settings = SettingsWindow(self.config, self._on_settings_saved)
            settings.show()

        self._settings_thread = threading.Thread(target=run_settings, daemon=True)
        self._settings_thread.start()

    def _on_settings_saved(self, config: Config) -> None:
        """Handle settings saved."""
        logger.info("Settings saved, updating components")
        self.config = config

        # Update components with new config
        self.hotkey.update_combination(config.hotkey.combination)
        self.hotkey.update_mode(config.hotkey.mode)
        self.transcriber.update_config(config.whisper)
        self.storage.update_config(config.storage)
        self.tray.update_transcriptions_folder(config.storage.transcriptions_path)

        logger.info(
            f"Updated settings. Hotkey: {config.hotkey.combination} "
            f"(mode: {config.hotkey.mode})"
        )

    def _quit(self) -> None:
        """Quit the application."""
        logger.info("Shutting down ElivroImagine")
        self._running = False
        self.hotkey.stop()
        self.tray.stop()

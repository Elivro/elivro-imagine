"""Main application orchestrator for ElivroImagine."""

from __future__ import annotations

import logging
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

from .classifier import ClassificationError, TaskClassification, classify_transcription
from .config import Config
from .devtracker import DevTrackerClient, DevTrackerError, find_duplicate_task
from .hotkey import HotkeyListener
from .clipboard import Paster
from .recorder import AudioRecorder
from .settings import SettingsWindow
from .sounds import init_mixer, play_start_sound, play_stop_sound
from .storage import InsufficientDiskSpaceError, StorageManager
from .transcriber import Transcriber, TranscriptionTimeoutError
from .tray import SystemTray
from .utils import SingleInstanceLock

if TYPE_CHECKING:
    from .splash import SplashScreen

logger = logging.getLogger(__name__)

# Max concurrent transcription threads
MAX_TRANSCRIPTION_WORKERS = 2


class ElivroImagineApp:
    """Main application class that orchestrates all components."""

    def __init__(self, splash: SplashScreen | None = None) -> None:
        """Initialize the application.

        Args:
            splash: Optional splash screen to update during initialization.
        """
        self._splash = splash
        self._update_splash("Loading configuration...")

        self._is_first_run = not Config.get_config_path().exists()
        self.config = Config.load()
        self.config.ensure_directories()
        self._setup_logging()

        logger.info("Initializing ElivroImagine v0.2.0")
        self._update_splash("Checking for other instances...")

        # Single instance lock
        self._instance_lock = SingleInstanceLock(
            self.config.get_config_dir() / "app.lock"
        )
        if not self._instance_lock.acquire():
            logger.error("Another instance of ElivroImagine is already running")
            print("ElivroImagine is already running.")
            sys.exit(1)

        # Thread pool for bounded concurrent transcriptions
        self._transcription_pool = ThreadPoolExecutor(
            max_workers=MAX_TRANSCRIPTION_WORKERS,
            thread_name_prefix="transcription",
        )

        # Initialize components with error handling
        self._update_splash("Initializing audio...")
        self.recorder = self._init_component(
            "AudioRecorder",
            lambda: AudioRecorder(self.config.recording),
        )
        self._update_splash("Setting up transcription engine...")
        self.transcriber = self._init_component(
            "Transcriber",
            lambda: Transcriber(
                self.config.whisper,
                transcription_config=self.config.transcription,
                on_progress=self._on_model_progress,
            ),
        )
        self._update_splash("Preparing storage...")
        self.storage = self._init_component(
            "StorageManager",
            lambda: StorageManager(self.config.storage),
        )

        # DevTracker client (optional, when enabled in settings)
        self._devtracker: DevTrackerClient | None = None
        if self.config.devtracker.enabled:
            self._devtracker = DevTrackerClient(self.config.devtracker)

        # Recording ownership: prevents multiple hotkeys from recording simultaneously
        self._recording_lock = threading.Lock()
        self._active_recording_source: str | None = None  # "save", "paste", or "devtracker"

        # Set up save hotkey listener
        self._update_splash("Configuring hotkeys...")
        self.hotkey = self._init_component(
            "HotkeyListener",
            lambda: HotkeyListener(
                combination=self.config.hotkey.combination,
                mode=self.config.hotkey.mode,
                on_start=self._on_save_recording_start,
                on_stop=self._on_save_recording_stop,
                scan_code=self.config.hotkey.scan_code,
            ),
        )

        # Set up paste hotkey listener
        self.paste_hotkey: HotkeyListener | None = None
        self.paster: Paster | None = None
        if self.config.paste_hotkey.enabled:
            self.paster = self._init_component(
                "Paster",
                lambda: Paster(
                    restore_clipboard=self.config.paste_hotkey.restore_clipboard,
                ),
            )
            self.paste_hotkey = self._init_component(
                "PasteHotkeyListener",
                lambda: HotkeyListener(
                    combination=self.config.paste_hotkey.combination,
                    mode=self.config.paste_hotkey.mode,
                    on_start=self._on_paste_recording_start,
                    on_stop=self._on_paste_recording_stop,
                    scan_code=self.config.paste_hotkey.scan_code,
                ),
            )

        # Set up devtracker hotkey listener (project-specific task creation)
        self.devtracker_hotkey: HotkeyListener | None = None
        if self.config.devtracker_hotkey.enabled and self.config.devtracker.enabled:
            self.devtracker_hotkey = self._init_component(
                "DevTrackerHotkeyListener",
                lambda: HotkeyListener(
                    combination=self.config.devtracker_hotkey.combination,
                    mode=self.config.devtracker_hotkey.mode,
                    on_start=self._on_devtracker_recording_start,
                    on_stop=self._on_devtracker_recording_stop,
                    scan_code=self.config.devtracker_hotkey.scan_code,
                ),
            )

        # Set up system tray
        self._update_splash("Setting up system tray...")
        transcriptions_folder = (
            self.storage.get_transcriptions_folder()
            if self.storage
            else self.config.storage.transcriptions_path
        )
        self.tray = self._init_component(
            "SystemTray",
            lambda: SystemTray(
                on_settings=self._show_settings,
                on_quit=self._quit,
                transcriptions_folder=transcriptions_folder,
            ),
        )

        # Set up recorder status callback
        if self.recorder:
            self.recorder.set_status_callback(self._on_recorder_status)

        self._running = False
        self._settings_thread: threading.Thread | None = None
        self._model_ready = threading.Event()  # Signals when model is loaded
        self._hotkey_capture_active = False  # Blocks recordings during settings capture

    def _update_splash(self, message: str) -> None:
        """Update splash screen message and process UI events.

        Args:
            message: Status message to display.
        """
        if self._splash:
            self._splash.update_message(message)
            self._splash.update()

    def _init_component(self, name: str, factory: object) -> object | None:
        """Initialize a component with error handling.

        Args:
            name: Component name for logging.
            factory: Callable that creates the component.

        Returns:
            The initialized component, or None if initialization failed.
        """
        try:
            return factory()  # type: ignore[operator]
        except Exception as e:
            logger.error(f"Failed to initialize {name}: {e}")
            return None

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

        # Initialize sound mixer eagerly so first play has no latency
        self._update_splash("Initializing sound system...")
        if self.config.sound.enabled:
            init_mixer()

        # Pre-load Whisper model in background (only for local backend)
        if self.transcriber and self.config.transcription.backend == "local":
            self._update_splash("Preparing AI model...")
            threading.Thread(target=self._preload_model, daemon=True).start()

        # Start components
        self._update_splash("Starting hotkey listeners...")
        if self.hotkey:
            self.hotkey.start()
        if self.paste_hotkey:
            self.paste_hotkey.start()
        if self.devtracker_hotkey:
            self.devtracker_hotkey.start()

        self._update_splash("Almost ready...")
        if self.tray:
            self.tray.start()

        # Don't close splash here - it closes when model finishes loading
        # For non-local backends or if transcriber is disabled, close now
        if not self.transcriber or self.config.transcription.backend != "local":
            if self._splash:
                self._splash.set_progress(100)
                self._splash.update_message("Ready to cook!")
                self._splash.update()
                import time
                time.sleep(0.3)
                self._splash.close()
                self._splash = None

        logger.info(
            f"ElivroImagine running. Hotkey: {self.config.hotkey.combination} "
            f"(mode: {self.config.hotkey.mode})"
        )
        if self.paste_hotkey:
            logger.info(
                f"Paste hotkey: {self.config.paste_hotkey.combination} "
                f"(mode: {self.config.paste_hotkey.mode})"
            )
        if self.devtracker_hotkey:
            logger.info(
                f"DevTracker hotkey: {self.config.devtracker_hotkey.combination} "
                f"(mode: {self.config.devtracker_hotkey.mode}, "
                f"project: {self.config.devtracker_hotkey.project})"
            )

        # First-run welcome notification
        if self._is_first_run and self.tray:
            self.tray.notify(
                "ElivroImagine",
                f"Ready! Press {self.config.hotkey.combination} to record. "
                "Right-click tray icon for settings.",
            )

        # Warn about degraded state
        degraded = []
        if not self.recorder:
            degraded.append("microphone")
        if not self.transcriber:
            degraded.append("transcription")
        if not self.storage:
            degraded.append("storage")
        if degraded and self.tray:
            self.tray.notify(
                "ElivroImagine Warning",
                f"Running with limited functionality: {', '.join(degraded)} unavailable",
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
        if not self.transcriber:
            self._model_ready.set()
            return
        logger.info("Pre-loading Whisper model...")
        model_error: str | None = None
        try:
            self.transcriber._ensure_model()
            logger.info("Whisper model ready")
        except Exception as e:
            logger.error(f"Failed to pre-load Whisper model: {e}")
            model_error = str(e)
        finally:
            # Signal that model loading is complete (success or failure)
            self._model_ready.set()
            # Close splash now that model is ready
            if self._splash:
                try:
                    self._splash.set_progress(100)
                    self._splash.update_message("Ready to cook!")
                    self._splash.update()
                    # Small delay to show "Ready" message
                    import time
                    time.sleep(0.5)
                    self._splash.close()
                except Exception:
                    pass  # Splash may already be closed
                self._splash = None

            # Notify user if model failed to load
            if model_error and self.tray:
                self.tray.notify(
                    "ElivroImagine",
                    f"Model failed to load: {model_error[:50]}"
                )

    def _on_model_progress(self, message: str) -> None:
        """Handle model loading progress updates."""
        logger.info(f"Model: {message}")
        # Forward to splash screen if still visible
        if self._splash:
            self._splash.update_message(message)
            self._splash.update()
        # Don't spam notifications for model progress - splash shows this
        # Only notify when model is fully ready
        if self.tray and "ready" in message.lower():
            self.tray.notify("ElivroImagine", message)

    def _do_recording_start(self, source: str) -> bool:
        """Start recording with ownership guard.

        Args:
            source: Recording source identifier ("save" or "paste").

        Returns:
            True if recording started, False if blocked.
        """
        # Block recordings during hotkey capture in settings
        if self._hotkey_capture_active:
            logger.debug("Recording blocked: hotkey capture in progress")
            return False

        if not self.recorder:
            logger.warning("Recording requested but recorder is unavailable")
            if self.tray:
                self.tray.notify(
                    "ElivroImagine Error", "Microphone is unavailable"
                )
            return False

        with self._recording_lock:
            if self._active_recording_source is not None:
                logger.warning(
                    f"Recording blocked: already recording for "
                    f"'{self._active_recording_source}'"
                )
                return False
            self._active_recording_source = source

        logger.info(f"Recording started (source: {source})")
        config = self.config  # Atomic reference read
        if config.sound.enabled:
            play_start_sound(config.sound.start_volume)
        if self.tray:
            self.tray.set_recording(True)
        self.recorder.start_recording()
        return True

    def _do_recording_stop(self, source: str) -> tuple[np.ndarray, float] | None:
        """Stop recording with ownership guard.

        Args:
            source: Recording source identifier ("save" or "paste").

        Returns:
            Tuple of (audio, duration) or None if no audio/wrong source.
        """
        if not self.recorder:
            return None

        with self._recording_lock:
            if self._active_recording_source != source:
                logger.debug(
                    f"Recording stop ignored: source '{source}' doesn't own "
                    f"recording (owner: '{self._active_recording_source}')"
                )
                return None
            self._active_recording_source = None

        logger.info(f"Recording stopped (source: {source})")

        # Play sound IMMEDIATELY - user feedback first
        config = self.config  # Atomic reference read
        if config.sound.enabled:
            play_stop_sound(config.sound.stop_volume)
        if self.tray:
            self.tray.set_recording(False)

        # Now stop recorder and process (can take time)
        result = self.recorder.stop_recording()
        if result is None:
            logger.warning("No audio recorded")
            if self.tray:
                self.tray.notify("ElivroImagine", "No audio recorded")
            return None

        audio, duration = result

        if duration < 0.5:
            logger.warning("Recording too short")
            if self.tray:
                self.tray.notify("ElivroImagine", "Recording too short (< 0.5s)")
            return None

        return audio, duration

    def _on_save_recording_start(self) -> None:
        """Handle save hotkey recording start."""
        self._do_recording_start("save")

    def _on_save_recording_stop(self) -> None:
        """Handle save hotkey recording stop."""
        result = self._do_recording_stop("save")
        if result is not None:
            audio, duration = result
            self._transcription_pool.submit(
                self._transcribe_and_save, audio, duration
            )

    def _on_paste_recording_start(self) -> None:
        """Handle paste hotkey recording start."""
        self._do_recording_start("paste")

    def _on_paste_recording_stop(self) -> None:
        """Handle paste hotkey recording stop."""
        result = self._do_recording_stop("paste")
        if result is not None:
            audio, duration = result
            self._transcription_pool.submit(
                self._transcribe_and_paste, audio, duration
            )

    def _on_devtracker_recording_start(self) -> None:
        """Handle devtracker hotkey recording start."""
        self._do_recording_start("devtracker")

    def _on_devtracker_recording_stop(self) -> None:
        """Handle devtracker hotkey recording stop."""
        result = self._do_recording_stop("devtracker")
        if result is not None:
            audio, duration = result
            project = self.config.devtracker_hotkey.project
            self._transcription_pool.submit(
                self._transcribe_and_create_project_task, audio, duration, project
            )

    def _transcribe_and_save(self, audio: np.ndarray, duration: float) -> None:
        """Transcribe audio and save to file or create DevTracker task."""
        if not self.transcriber:
            logger.error("Transcriber unavailable")
            if self.tray:
                self.tray.notify(
                    "ElivroImagine Error", "Transcription service unavailable"
                )
            return

        if self.tray:
            self.tray.set_transcribing(True)

        try:
            logger.info(f"Transcribing {duration:.1f}s of audio...")

            text = self.transcriber.transcribe(
                audio, self.config.recording.sample_rate
            )

            if not text.strip():
                logger.warning("Transcription returned empty text")
                if self.tray:
                    self.tray.notify("ElivroImagine", "No speech detected")
                return

            # DevTracker path: classify and create task
            if self._devtracker:
                self._create_devtracker_task(text)
                return

            # Fallback: save to file
            if not self.storage:
                logger.error("Storage unavailable")
                if self.tray:
                    self.tray.notify("ElivroImagine Error", "Storage unavailable")
                return

            filepath = self.storage.save_transcription(text, duration)
            logger.info(f"Saved transcription to {filepath}")

            preview = text[:100] + "..." if len(text) > 100 else text
            if self.tray:
                self.tray.notify("Transcription Saved", preview)

        except TranscriptionTimeoutError:
            logger.error("Transcription timed out")
            if self.tray:
                self.tray.notify(
                    "ElivroImagine Error",
                    "Transcription timed out. Try a shorter recording.",
                )

        except InsufficientDiskSpaceError as e:
            logger.error(f"Insufficient disk space: {e}")
            if self.tray:
                self.tray.notify("ElivroImagine Error", str(e))

        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            if self.tray:
                self.tray.notify(
                    "ElivroImagine Error", f"Transcription failed: {e}"
                )

        finally:
            if self.tray:
                self.tray.set_transcribing(False)

    def _create_devtracker_task(
        self, text: str, project_override: str | None = None
    ) -> None:
        """Classify transcription and create or update a DevTracker task.

        Args:
            text: Transcribed text to classify and submit.
            project_override: If set, use this project instead of the default.
        """
        if not self._devtracker:
            return

        try:
            # Fetch project categories for accurate classification
            try:
                category_names = self._devtracker.get_category_names()
            except DevTrackerError:
                category_names = None  # LLM picks freely if API fails

            # Classify (and translate if needed)
            api_key = self.config.transcription.berget_api_key
            classification = classify_transcription(
                text, api_key, categories=category_names
            )
            logger.info(
                f"Classified: intent={classification.intent}, "
                f"title='{classification.title}' "
                f"[{classification.category}/{classification.priority}]"
            )

            if classification.intent == "update":
                self._update_devtracker_task(classification, project_override)
            else:
                self._do_create_devtracker_task(classification, project_override)

        except ClassificationError as e:
            logger.error(f"Classification failed: {e}")
            if self.tray:
                self.tray.notify("ElivroImagine Error", f"Classification failed: {e}")

        except DevTrackerError as e:
            logger.error(f"DevTracker error: {e}")
            if self.tray:
                self.tray.notify("ElivroImagine Error", f"DevTracker: {e}")

        except Exception as e:
            logger.error(f"Task creation failed: {e}")
            if self.tray:
                self.tray.notify("ElivroImagine Error", f"Task failed: {e}")

    def _do_create_devtracker_task(
        self,
        classification: TaskClassification,
        project_override: str | None = None,
    ) -> None:
        """Create a new DevTracker task from classification.

        Args:
            classification: Classified task data.
            project_override: If set, create the task on this project instead of the default.
        """
        if not self._devtracker:
            return

        # Duplicate check
        existing = self._devtracker.get_active_and_backlog_tasks()
        duplicate = find_duplicate_task(classification.title, existing)
        if duplicate:
            dup_id = duplicate.get("id", "?")
            dup_title = duplicate.get("title", "")
            logger.info(f"Duplicate found: #{dup_id} {dup_title}")
            if self.tray:
                self.tray.notify(
                    "Duplicate Task",
                    f"Matches #{dup_id}: {dup_title}",
                )
            return

        # Resolve category ID
        category_id = self._devtracker.get_category_id(classification.category)

        # Create task
        task = self._devtracker.create_task(
            title=classification.title,
            description=classification.description,
            category=category_id,
            priority=classification.priority,
            effort=classification.effort,
            project_override=project_override,
        )

        project_label = project_override or self.config.devtracker.project
        task_id = task.get("id", "?")
        logger.info(f"Created task #{task_id} ({project_label}): {classification.title}")
        if self.tray:
            self.tray.notify(
                f"Task Created ({project_label})",
                f"#{task_id}: {classification.title}",
            )

    def _update_devtracker_task(
        self,
        classification: TaskClassification,
        project_override: str | None = None,
    ) -> None:
        """Update an existing DevTracker task from classification.

        Args:
            classification: Classified task data with task_id and changed fields.
            project_override: If set, use this project label in notifications.
        """
        if not self._devtracker:
            return

        # Resolve category ID only if category is being changed
        category_id: int | None = None
        if classification.category is not None:
            category_id = self._devtracker.get_category_id(classification.category)

        # Build list of changed field names for notification
        changed_fields: list[str] = []
        if classification.title is not None:
            changed_fields.append("title")
        if classification.description is not None:
            changed_fields.append("description")
        if classification.category is not None:
            changed_fields.append("category")
        if classification.priority is not None:
            changed_fields.append("priority")
        if classification.effort is not None:
            changed_fields.append("effort")

        task = self._devtracker.update_task(
            task_id=classification.task_id,
            title=classification.title,
            description=classification.description,
            category=category_id,
            priority=classification.priority,
            effort=classification.effort,
        )

        project_label = project_override or self.config.devtracker.project
        task_id = classification.task_id
        fields_str = ", ".join(changed_fields)
        logger.info(
            f"Updated task #{task_id} ({project_label}): {fields_str}"
        )
        if self.tray:
            self.tray.notify(
                f"Task Updated ({project_label})",
                f"#{task_id}: updated {fields_str}",
            )

    def _transcribe_and_create_project_task(
        self, audio: np.ndarray, duration: float, project: str
    ) -> None:
        """Transcribe audio and create a DevTracker task for a specific project.

        Args:
            audio: Audio data to transcribe.
            duration: Duration of the recording in seconds.
            project: Target project name for the task.
        """
        if not self.transcriber:
            logger.error("Transcriber unavailable")
            if self.tray:
                self.tray.notify(
                    "ElivroImagine Error", "Transcription service unavailable"
                )
            return

        if self.tray:
            self.tray.set_transcribing(True)

        try:
            logger.info(f"Transcribing {duration:.1f}s of audio for {project} task...")

            text = self.transcriber.transcribe(
                audio, self.config.recording.sample_rate
            )

            if not text.strip():
                logger.warning("Transcription returned empty text")
                if self.tray:
                    self.tray.notify("ElivroImagine", "No speech detected")
                return

            self._create_devtracker_task(text, project_override=project)

        except TranscriptionTimeoutError:
            logger.error("Transcription timed out")
            if self.tray:
                self.tray.notify(
                    "ElivroImagine Error",
                    "Transcription timed out. Try a shorter recording.",
                )

        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            if self.tray:
                self.tray.notify(
                    "ElivroImagine Error", f"Transcription failed: {e}"
                )

        finally:
            if self.tray:
                self.tray.set_transcribing(False)

    def _transcribe_and_paste(self, audio: np.ndarray, duration: float) -> None:
        """Transcribe audio and paste into focused field."""
        if not self.transcriber or not self.paster:
            logger.error("Transcriber or paster unavailable")
            if self.tray:
                self.tray.notify("ElivroImagine", "Paste unavailable")
            return

        if self.tray:
            self.tray.set_transcribing(True)

        try:
            logger.info(f"Transcribing {duration:.1f}s of audio for paste...")

            text = self.transcriber.transcribe(
                audio, self.config.recording.sample_rate
            )

            if not text.strip():
                logger.warning("Transcription returned empty text")
                if self.tray:
                    self.tray.notify("ElivroImagine", "No speech detected")
                return

            success = self.paster.paste_text(text)
            if success:
                preview = text[:100] + "..." if len(text) > 100 else text
                logger.info(f"Pasted transcription: {preview}")
            else:
                logger.error("Failed to paste text")
                if self.tray:
                    self.tray.notify("ElivroImagine", "Failed to paste text")

        except TranscriptionTimeoutError:
            logger.error("Transcription timed out")
            if self.tray:
                self.tray.notify("ElivroImagine", "Transcription timed out")

        except Exception as e:
            logger.error(f"Transcribe-and-paste failed: {e}")
            if self.tray:
                self.tray.notify("ElivroImagine", f"Paste failed: {e}")

        finally:
            if self.tray:
                self.tray.set_transcribing(False)

    def _on_recorder_status(self, status: str) -> None:
        """Handle recorder status changes."""
        logger.debug(f"Recorder status: {status}")
        if status.startswith("error:") or status.startswith("warning:"):
            if self.tray:
                self.tray.notify("ElivroImagine", status)

    def _show_settings(self) -> None:
        """Show settings window."""
        if self._settings_thread and self._settings_thread.is_alive():
            return

        def run_settings() -> None:
            settings = SettingsWindow(
                self.config,
                self._on_settings_saved,
                on_capture_state_changed=self._on_hotkey_capture_state_changed,
            )
            settings.show()

        self._settings_thread = threading.Thread(target=run_settings, daemon=True)
        self._settings_thread.start()

    def _on_hotkey_capture_state_changed(self, capturing: bool) -> None:
        """Handle hotkey capture state changes from settings window.

        Args:
            capturing: True if capture started, False if capture ended.
        """
        self._hotkey_capture_active = capturing
        logger.debug(f"Hotkey capture active: {capturing}")

    def _on_settings_saved(self, config: Config) -> None:
        """Handle settings saved."""
        logger.info("Settings saved, updating components")
        self.config = config

        # Update components with new config
        if self.hotkey:
            self.hotkey.update_combination(
                config.hotkey.combination, config.hotkey.scan_code
            )
            self.hotkey.update_mode(config.hotkey.mode)

        # Update paste hotkey
        if config.paste_hotkey.enabled:
            if self.paste_hotkey is None:
                # Create new paste hotkey listener
                self.paster = Paster(
                    restore_clipboard=config.paste_hotkey.restore_clipboard,
                )
                self.paste_hotkey = HotkeyListener(
                    combination=config.paste_hotkey.combination,
                    mode=config.paste_hotkey.mode,
                    on_start=self._on_paste_recording_start,
                    on_stop=self._on_paste_recording_stop,
                    scan_code=config.paste_hotkey.scan_code,
                )
                self.paste_hotkey.start()
            else:
                self.paste_hotkey.update_combination(
                    config.paste_hotkey.combination, config.paste_hotkey.scan_code
                )
                self.paste_hotkey.update_mode(config.paste_hotkey.mode)
                if self.paster:
                    self.paster.restore_clipboard = config.paste_hotkey.restore_clipboard
        else:
            # Disable paste hotkey
            if self.paste_hotkey:
                self.paste_hotkey.stop()
                self.paste_hotkey = None
                self.paster = None

        if self.transcriber:
            self.transcriber.update_config(config.whisper)
            self.transcriber.update_transcription_config(config.transcription)

        # Update DevTracker client
        if config.devtracker.enabled:
            if self._devtracker:
                self._devtracker.update_config(config.devtracker)
            else:
                self._devtracker = DevTrackerClient(config.devtracker)
        else:
            self._devtracker = None

        # Update devtracker hotkey (requires both devtracker and devtracker_hotkey enabled)
        if config.devtracker_hotkey.enabled and config.devtracker.enabled:
            if self.devtracker_hotkey is None:
                self.devtracker_hotkey = HotkeyListener(
                    combination=config.devtracker_hotkey.combination,
                    mode=config.devtracker_hotkey.mode,
                    on_start=self._on_devtracker_recording_start,
                    on_stop=self._on_devtracker_recording_stop,
                    scan_code=config.devtracker_hotkey.scan_code,
                )
                self.devtracker_hotkey.start()
            else:
                self.devtracker_hotkey.update_combination(
                    config.devtracker_hotkey.combination,
                    config.devtracker_hotkey.scan_code,
                )
                self.devtracker_hotkey.update_mode(config.devtracker_hotkey.mode)
        else:
            if self.devtracker_hotkey:
                self.devtracker_hotkey.stop()
                self.devtracker_hotkey = None

        if self.storage:
            self.storage.update_config(config.storage)
        if self.tray:
            self.tray.update_transcriptions_folder(config.storage.transcriptions_path)

        # Update Windows autostart setting
        if sys.platform == "win32":
            from .windows import WindowsStartupManager

            manager = WindowsStartupManager()
            if config.startup.start_with_windows:
                manager.enable_autostart()
            else:
                manager.disable_autostart()

        logger.info(
            f"Updated settings. Hotkey: {config.hotkey.combination} "
            f"(mode: {config.hotkey.mode}), "
            f"Language: {config.whisper.language}"
        )

    def _quit(self) -> None:
        """Quit the application."""
        logger.info("Shutting down ElivroImagine")
        self._running = False

        # Stop recording if in progress
        if self.recorder and self.recorder.is_recording:
            self.recorder.stop_recording()

        # Shutdown transcription pool (cancel pending, don't block on active)
        self._transcription_pool.shutdown(wait=False, cancel_futures=True)

        # Stop components
        if self.hotkey:
            self.hotkey.stop()
        if self.paste_hotkey:
            self.paste_hotkey.stop()
        if self.devtracker_hotkey:
            self.devtracker_hotkey.stop()
        if self.tray:
            self.tray.stop()

        # Cleanup sounds
        from .sounds import cleanup_mixer

        cleanup_mixer()

        # Wait for settings thread
        if self._settings_thread and self._settings_thread.is_alive():
            self._settings_thread.join(timeout=1.0)

        # Release instance lock
        self._instance_lock.release()

        logger.info("ElivroImagine shutdown complete")

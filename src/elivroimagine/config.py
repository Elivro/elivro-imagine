"""Configuration management for ElivroImagine."""

import logging
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import yaml

logger = logging.getLogger(__name__)

# Supported transcription languages: (code, display_name)
# "auto" enables automatic language detection
SUPPORTED_LANGUAGES: list[tuple[str, str]] = [
    ("auto", "Auto-detect"),
    ("en", "English"),
    ("sv", "Swedish"),
]


@dataclass
class HotkeyConfig:
    """Hotkey configuration."""

    combination: str = "<ctrl>+<alt>+r"
    scan_code: int | None = None  # For layout-independent keys (e.g., § on Swedish keyboards)
    mode: Literal["hold", "toggle"] = "hold"


@dataclass
class RecordingConfig:
    """Recording configuration."""

    sample_rate: int = 16000
    max_duration_seconds: int = 120
    microphone_id: str | None = None  # None = system default

    def __post_init__(self) -> None:
        """Validate recording configuration."""
        valid_rates = [8000, 16000, 22050, 44100, 48000]
        if self.sample_rate not in valid_rates:
            self.sample_rate = 16000
        if self.max_duration_seconds < 1:
            self.max_duration_seconds = 1
        elif self.max_duration_seconds > 600:
            self.max_duration_seconds = 600


@dataclass
class WhisperConfig:
    """Whisper model configuration."""

    model_size: Literal["tiny", "base", "small", "medium", "large"] = "small"
    language: str = "auto"  # "auto" for auto-detection, or specific language code
    transcription_timeout_seconds: int = 300

    def __post_init__(self) -> None:
        """Validate whisper configuration."""
        valid_langs = [code for code, _ in SUPPORTED_LANGUAGES]
        if self.language not in valid_langs:
            self.language = "auto"
        if self.transcription_timeout_seconds < 10:
            self.transcription_timeout_seconds = 10
        elif self.transcription_timeout_seconds > 600:
            self.transcription_timeout_seconds = 600


@dataclass
class StorageConfig:
    """Storage configuration."""

    transcriptions_dir: str = "~/.elivroimagine/transcriptions"

    @property
    def transcriptions_path(self) -> Path:
        """Get resolved transcriptions directory path."""
        return Path(self.transcriptions_dir).expanduser()

    @property
    def archive_path(self) -> Path:
        """Get archive directory path."""
        return self.transcriptions_path / "archive"


@dataclass
class PasteHotkeyConfig:
    """Paste hotkey configuration."""

    enabled: bool = False
    combination: str = "<shift>+<mouse_middle>"
    scan_code: int | None = None  # For layout-independent keys
    mode: Literal["hold", "toggle"] = "hold"
    restore_clipboard: bool = False  # Keep transcription in clipboard for Win+V


@dataclass
class TranscriptionConfig:
    """Transcription backend configuration."""

    backend: Literal["local", "berget"] = "local"
    berget_api_key: str = ""


@dataclass
class DevTrackerConfig:
    """DevTracker integration configuration."""

    enabled: bool = False
    api_key: str = ""
    email: str = ""
    project: str = ""
    api_url: str = "https://basen.elivro.se/internal/api/dev-tracker"


@dataclass
class DevTrackerHotkeyConfig:
    """DevTracker hotkey configuration for project-specific task creation."""

    enabled: bool = False
    combination: str = "<ctrl>+<alt>+i"
    scan_code: int | None = None
    mode: Literal["hold", "toggle"] = "hold"
    project: str = "intranet"


@dataclass
class StartupConfig:
    """Startup configuration."""

    start_with_windows: bool = False


@dataclass
class SoundConfig:
    """Sound feedback configuration."""

    start_volume: float = 1.0  # 0.0 to 1.0
    stop_volume: float = 0.7  # 0.0 to 1.0
    enabled: bool = True  # Master toggle

    def __post_init__(self) -> None:
        """Clamp volume values to valid range."""
        self.start_volume = max(0.0, min(1.0, self.start_volume))
        self.stop_volume = max(0.0, min(1.0, self.stop_volume))


@dataclass
class Config:
    """Main application configuration."""

    hotkey: HotkeyConfig = field(default_factory=HotkeyConfig)
    paste_hotkey: PasteHotkeyConfig = field(default_factory=PasteHotkeyConfig)
    recording: RecordingConfig = field(default_factory=RecordingConfig)
    whisper: WhisperConfig = field(default_factory=WhisperConfig)
    transcription: TranscriptionConfig = field(default_factory=TranscriptionConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    startup: StartupConfig = field(default_factory=StartupConfig)
    sound: SoundConfig = field(default_factory=SoundConfig)
    devtracker: DevTrackerConfig = field(default_factory=DevTrackerConfig)
    devtracker_hotkey: DevTrackerHotkeyConfig = field(default_factory=DevTrackerHotkeyConfig)

    @classmethod
    def get_config_dir(cls) -> Path:
        """Get the configuration directory."""
        return Path.home() / ".elivroimagine"

    @classmethod
    def get_config_path(cls) -> Path:
        """Get the configuration file path."""
        return cls.get_config_dir() / "config.yaml"

    @classmethod
    def load(cls) -> "Config":
        """Load configuration from file or create default."""
        config_path = cls.get_config_path()

        if not config_path.exists():
            config = cls()
            config.save()
            return config

        try:
            with open(config_path, encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
        except yaml.YAMLError as e:
            logger.error(f"Failed to parse config: {e}. Using defaults.")
            # Backup corrupted config
            backup_path = config_path.with_suffix(".yaml.bak")
            try:
                shutil.copy2(config_path, backup_path)
            except Exception:
                pass
            return cls()
        except Exception as e:
            logger.error(f"Failed to load config: {e}. Using defaults.")
            return cls()

        try:
            return cls(
                hotkey=HotkeyConfig(**data.get("hotkey", {})),
                paste_hotkey=PasteHotkeyConfig(**data.get("paste_hotkey", {})),
                recording=RecordingConfig(**data.get("recording", {})),
                whisper=WhisperConfig(**data.get("whisper", {})),
                transcription=TranscriptionConfig(**data.get("transcription", {})),
                storage=StorageConfig(**data.get("storage", {})),
                startup=StartupConfig(**data.get("startup", {})),
                sound=SoundConfig(**data.get("sound", {})),
                devtracker=DevTrackerConfig(**data.get("devtracker", {})),
                devtracker_hotkey=DevTrackerHotkeyConfig(**data.get("devtracker_hotkey", {})),
            )
        except TypeError as e:
            logger.error(f"Invalid config structure: {e}. Using defaults.")
            return cls()

    def save(self) -> None:
        """Save configuration to file."""
        config_path = self.get_config_path()
        config_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "hotkey": {
                "combination": self.hotkey.combination,
                "scan_code": self.hotkey.scan_code,
                "mode": self.hotkey.mode,
            },
            "paste_hotkey": {
                "enabled": self.paste_hotkey.enabled,
                "combination": self.paste_hotkey.combination,
                "scan_code": self.paste_hotkey.scan_code,
                "mode": self.paste_hotkey.mode,
                "restore_clipboard": self.paste_hotkey.restore_clipboard,
            },
            "recording": {
                "sample_rate": self.recording.sample_rate,
                "max_duration_seconds": self.recording.max_duration_seconds,
                "microphone_id": self.recording.microphone_id,
            },
            "whisper": {
                "model_size": self.whisper.model_size,
                "language": self.whisper.language,
                "transcription_timeout_seconds": self.whisper.transcription_timeout_seconds,
            },
            "transcription": {
                "backend": self.transcription.backend,
                "berget_api_key": self.transcription.berget_api_key,
            },
            "storage": {
                "transcriptions_dir": self.storage.transcriptions_dir,
            },
            "startup": {
                "start_with_windows": self.startup.start_with_windows,
            },
            "sound": {
                "start_volume": self.sound.start_volume,
                "stop_volume": self.sound.stop_volume,
                "enabled": self.sound.enabled,
            },
            "devtracker": {
                "enabled": self.devtracker.enabled,
                "api_key": self.devtracker.api_key,
                "email": self.devtracker.email,
                "project": self.devtracker.project,
                "api_url": self.devtracker.api_url,
            },
            "devtracker_hotkey": {
                "enabled": self.devtracker_hotkey.enabled,
                "combination": self.devtracker_hotkey.combination,
                "scan_code": self.devtracker_hotkey.scan_code,
                "mode": self.devtracker_hotkey.mode,
                "project": self.devtracker_hotkey.project,
            },
        }

        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)

    def ensure_directories(self) -> None:
        """Create necessary directories if they don't exist."""
        self.get_config_dir().mkdir(parents=True, exist_ok=True)
        self.storage.transcriptions_path.mkdir(parents=True, exist_ok=True)
        self.storage.archive_path.mkdir(parents=True, exist_ok=True)
        (self.get_config_dir() / "logs").mkdir(parents=True, exist_ok=True)

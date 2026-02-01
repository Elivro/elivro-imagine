"""Configuration management for ElivroImagine."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import yaml


@dataclass
class HotkeyConfig:
    """Hotkey configuration."""

    combination: str = "<ctrl>+<alt>+r"
    mode: Literal["hold", "toggle"] = "hold"


@dataclass
class RecordingConfig:
    """Recording configuration."""

    sample_rate: int = 16000
    max_duration_seconds: int = 120


@dataclass
class WhisperConfig:
    """Whisper model configuration."""

    model_size: Literal["tiny", "base", "small", "medium"] = "small"
    language: str | None = "en"


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
class StartupConfig:
    """Startup configuration."""

    start_with_windows: bool = False


@dataclass
class Config:
    """Main application configuration."""

    hotkey: HotkeyConfig = field(default_factory=HotkeyConfig)
    recording: RecordingConfig = field(default_factory=RecordingConfig)
    whisper: WhisperConfig = field(default_factory=WhisperConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    startup: StartupConfig = field(default_factory=StartupConfig)

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

        with open(config_path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        return cls(
            hotkey=HotkeyConfig(**data.get("hotkey", {})),
            recording=RecordingConfig(**data.get("recording", {})),
            whisper=WhisperConfig(**data.get("whisper", {})),
            storage=StorageConfig(**data.get("storage", {})),
            startup=StartupConfig(**data.get("startup", {})),
        )

    def save(self) -> None:
        """Save configuration to file."""
        config_path = self.get_config_path()
        config_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "hotkey": {
                "combination": self.hotkey.combination,
                "mode": self.hotkey.mode,
            },
            "recording": {
                "sample_rate": self.recording.sample_rate,
                "max_duration_seconds": self.recording.max_duration_seconds,
            },
            "whisper": {
                "model_size": self.whisper.model_size,
                "language": self.whisper.language,
            },
            "storage": {
                "transcriptions_dir": self.storage.transcriptions_dir,
            },
            "startup": {
                "start_with_windows": self.startup.start_with_windows,
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

"""Tests for configuration management."""

from pathlib import Path
from unittest.mock import patch

import pytest
import yaml


class TestConfigLoad:
    """Test config loading functionality."""

    def test_load_creates_default_config_if_missing(
        self, temp_config_dir: Path
    ) -> None:
        """Loading config creates default if file doesn't exist."""
        from elivroimagine.config import Config

        config_path = temp_config_dir / "config.yaml"

        with patch.object(Config, "get_config_path", return_value=config_path):
            config = Config.load()

            # Should have created the file
            assert config_path.exists()

            # Should have default values
            assert config.hotkey.combination == "<ctrl>+<alt>+r"
            assert config.hotkey.mode == "hold"
            assert config.whisper.model_size == "small"

    def test_load_reads_existing_config(self, temp_config_dir: Path) -> None:
        """Loading config reads existing values."""
        from elivroimagine.config import Config

        config_path = temp_config_dir / "config.yaml"

        # Create custom config
        custom_config = {
            "hotkey": {"combination": "<ctrl>+<shift>+v", "mode": "toggle"},
            "whisper": {"model_size": "tiny", "language": "sv"},
        }
        with open(config_path, "w") as f:
            yaml.dump(custom_config, f)

        with patch.object(Config, "get_config_path", return_value=config_path):
            config = Config.load()

            assert config.hotkey.combination == "<ctrl>+<shift>+v"
            assert config.hotkey.mode == "toggle"
            assert config.whisper.model_size == "tiny"
            assert config.whisper.language == "sv"

    def test_load_handles_partial_config(self, temp_config_dir: Path) -> None:
        """Loading handles config with only some values set."""
        from elivroimagine.config import Config

        config_path = temp_config_dir / "config.yaml"

        # Create partial config (only hotkey section)
        partial_config = {"hotkey": {"combination": "<ctrl>+r"}}
        with open(config_path, "w") as f:
            yaml.dump(partial_config, f)

        with patch.object(Config, "get_config_path", return_value=config_path):
            config = Config.load()

            # Custom value should be loaded
            assert config.hotkey.combination == "<ctrl>+r"

            # Missing value should use default
            assert config.hotkey.mode == "hold"

            # Other sections should use defaults
            assert config.whisper.model_size == "small"


class TestConfigSave:
    """Test config saving functionality."""

    def test_save_writes_all_sections(self, temp_config_dir: Path) -> None:
        """Saving writes all config sections."""
        from elivroimagine.config import Config

        config_path = temp_config_dir / "config.yaml"

        with patch.object(Config, "get_config_path", return_value=config_path):
            config = Config()
            config.hotkey.combination = "<ctrl>+<alt>+x"
            config.whisper.model_size = "medium"
            config.save()

            # Read back and verify
            with open(config_path) as f:
                data = yaml.safe_load(f)

            assert data["hotkey"]["combination"] == "<ctrl>+<alt>+x"
            assert data["whisper"]["model_size"] == "medium"

    def test_save_creates_parent_directories(self, tmp_path: Path) -> None:
        """Saving creates parent directories if needed."""
        from elivroimagine.config import Config

        config_path = tmp_path / "nested" / "dir" / "config.yaml"

        with patch.object(Config, "get_config_path", return_value=config_path):
            config = Config()
            config.save()

            assert config_path.exists()


class TestConfigDataclasses:
    """Test config dataclass behavior."""

    def test_storage_config_transcriptions_path(self) -> None:
        """StorageConfig expands ~ in transcriptions path."""
        from elivroimagine.config import StorageConfig

        config = StorageConfig(transcriptions_dir="~/.elivroimagine/transcriptions")

        path = config.transcriptions_path
        assert "~" not in str(path)
        assert path.is_absolute()

    def test_storage_config_archive_path(self) -> None:
        """StorageConfig provides archive subdirectory."""
        from elivroimagine.config import StorageConfig

        config = StorageConfig(transcriptions_dir="~/.elivroimagine/transcriptions")

        assert config.archive_path == config.transcriptions_path / "archive"

    def test_config_ensure_directories(self, temp_config_dir: Path) -> None:
        """ensure_directories creates all required directories."""
        from elivroimagine.config import Config

        with patch.object(Config, "get_config_dir", return_value=temp_config_dir):
            config = Config()
            config.storage.transcriptions_dir = str(temp_config_dir / "transcriptions")
            config.ensure_directories()

            assert (temp_config_dir / "transcriptions").exists()
            assert (temp_config_dir / "transcriptions" / "archive").exists()
            assert (temp_config_dir / "logs").exists()


class TestSoundConfigValidation:
    """Test SoundConfig volume validation."""

    def test_volume_clamped_to_max(self) -> None:
        """Volume above 1.0 is clamped to 1.0."""
        from elivroimagine.config import SoundConfig

        config = SoundConfig(start_volume=1.5, stop_volume=2.0)

        assert config.start_volume == 1.0
        assert config.stop_volume == 1.0

    def test_volume_clamped_to_min(self) -> None:
        """Volume below 0.0 is clamped to 0.0."""
        from elivroimagine.config import SoundConfig

        config = SoundConfig(start_volume=-0.5, stop_volume=-1.0)

        assert config.start_volume == 0.0
        assert config.stop_volume == 0.0

    def test_valid_volume_unchanged(self) -> None:
        """Valid volume values are unchanged."""
        from elivroimagine.config import SoundConfig

        config = SoundConfig(start_volume=0.5, stop_volume=0.7)

        assert config.start_volume == 0.5
        assert config.stop_volume == 0.7


class TestRecordingConfigValidation:
    """Test RecordingConfig validation."""

    def test_invalid_sample_rate_uses_default(self) -> None:
        """Invalid sample rate is replaced with default."""
        from elivroimagine.config import RecordingConfig

        config = RecordingConfig(sample_rate=12345)

        assert config.sample_rate == 16000

    def test_valid_sample_rates_accepted(self) -> None:
        """Valid sample rates are accepted."""
        from elivroimagine.config import RecordingConfig

        for rate in [8000, 16000, 22050, 44100, 48000]:
            config = RecordingConfig(sample_rate=rate)
            assert config.sample_rate == rate

    def test_max_duration_minimum(self) -> None:
        """Max duration below 1 is clamped to 1."""
        from elivroimagine.config import RecordingConfig

        config = RecordingConfig(max_duration_seconds=0)

        assert config.max_duration_seconds == 1

    def test_max_duration_maximum(self) -> None:
        """Max duration above 600 is clamped to 600."""
        from elivroimagine.config import RecordingConfig

        config = RecordingConfig(max_duration_seconds=1000)

        assert config.max_duration_seconds == 600

    def test_valid_max_duration_unchanged(self) -> None:
        """Valid max duration is unchanged."""
        from elivroimagine.config import RecordingConfig

        config = RecordingConfig(max_duration_seconds=120)

        assert config.max_duration_seconds == 120


class TestConfigErrorHandling:
    """Test config error handling."""

    def test_malformed_yaml_uses_defaults(self, temp_config_dir: Path) -> None:
        """Malformed YAML falls back to defaults."""
        from elivroimagine.config import Config

        config_path = temp_config_dir / "config.yaml"

        # Write invalid YAML
        with open(config_path, "w") as f:
            f.write("{ invalid yaml: [unclosed")

        with patch.object(Config, "get_config_path", return_value=config_path):
            config = Config.load()

            # Should use defaults
            assert config.hotkey.combination == "<ctrl>+<alt>+r"
            assert config.whisper.model_size == "small"

    def test_malformed_yaml_creates_backup(self, temp_config_dir: Path) -> None:
        """Malformed YAML creates a backup file."""
        from elivroimagine.config import Config

        config_path = temp_config_dir / "config.yaml"

        # Write invalid YAML
        with open(config_path, "w") as f:
            f.write("{ invalid yaml: [unclosed")

        with patch.object(Config, "get_config_path", return_value=config_path):
            Config.load()

            # Backup should exist
            backup_path = config_path.with_suffix(".yaml.bak")
            assert backup_path.exists()

    def test_invalid_config_structure_uses_defaults(
        self, temp_config_dir: Path
    ) -> None:
        """Invalid config structure falls back to defaults."""
        from elivroimagine.config import Config

        config_path = temp_config_dir / "config.yaml"

        # Write valid YAML but invalid structure (extra keys that cause TypeError)
        with open(config_path, "w") as f:
            yaml.dump({"hotkey": {"invalid_key": "value", "mode": "hold"}}, f)

        with patch.object(Config, "get_config_path", return_value=config_path):
            config = Config.load()

            # Should use defaults
            assert config.hotkey.combination == "<ctrl>+<alt>+r"

    def test_io_error_uses_defaults(self, temp_config_dir: Path) -> None:
        """IO error when reading config falls back to defaults."""
        from elivroimagine.config import Config

        config_path = temp_config_dir / "config.yaml"
        config_path.touch()

        with patch.object(Config, "get_config_path", return_value=config_path):
            with patch("builtins.open", side_effect=IOError("Permission denied")):
                config = Config.load()

                # Should use defaults
                assert config.hotkey.combination == "<ctrl>+<alt>+r"


class TestWhisperConfigValidation:
    """Test WhisperConfig validation."""

    def test_valid_language_accepted(self) -> None:
        """Valid languages (auto, en, sv) are accepted."""
        from elivroimagine.config import WhisperConfig

        config = WhisperConfig(language="auto")
        assert config.language == "auto"

        config = WhisperConfig(language="en")
        assert config.language == "en"

        config = WhisperConfig(language="sv")
        assert config.language == "sv"

    def test_invalid_language_defaults_to_auto(self) -> None:
        """Invalid language codes fall back to auto-detect."""
        from elivroimagine.config import WhisperConfig

        config = WhisperConfig(language="xx")
        assert config.language == "auto"

    def test_timeout_minimum(self) -> None:
        """Timeout below 10 is clamped to 10."""
        from elivroimagine.config import WhisperConfig

        config = WhisperConfig(transcription_timeout_seconds=1)
        assert config.transcription_timeout_seconds == 10

    def test_timeout_maximum(self) -> None:
        """Timeout above 600 is clamped to 600."""
        from elivroimagine.config import WhisperConfig

        config = WhisperConfig(transcription_timeout_seconds=9999)
        assert config.transcription_timeout_seconds == 600

    def test_valid_timeout_unchanged(self) -> None:
        """Valid timeout values are unchanged."""
        from elivroimagine.config import WhisperConfig

        config = WhisperConfig(transcription_timeout_seconds=300)
        assert config.transcription_timeout_seconds == 300

    def test_config_saves_language(self, temp_config_dir: Path) -> None:
        """Language is persisted in config file."""
        from elivroimagine.config import Config

        config_path = temp_config_dir / "config.yaml"

        with patch.object(Config, "get_config_path", return_value=config_path):
            config = Config()
            config.whisper.language = "sv"
            config.save()

            # Read back
            loaded = Config.load()
            assert loaded.whisper.language == "sv"


class TestPasteHotkeyConfig:
    """Test PasteHotkeyConfig defaults and persistence."""

    def test_default_values(self) -> None:
        """PasteHotkeyConfig has correct defaults."""
        from elivroimagine.config import PasteHotkeyConfig

        config = PasteHotkeyConfig()

        assert config.enabled is False
        assert config.combination == "<shift>+<mouse_middle>"
        assert config.mode == "hold"
        assert config.restore_clipboard is False  # Keep transcription in clipboard

    def test_config_has_paste_hotkey(self) -> None:
        """Config includes paste_hotkey field with defaults."""
        from elivroimagine.config import Config

        config = Config()

        assert config.paste_hotkey.enabled is False
        assert config.paste_hotkey.combination == "<shift>+<mouse_middle>"

    def test_backward_compat_missing_section(self, temp_config_dir: Path) -> None:
        """Config without paste_hotkey section loads with defaults."""
        from elivroimagine.config import Config

        config_path = temp_config_dir / "config.yaml"

        # Old config without paste_hotkey section
        old_config = {
            "hotkey": {"combination": "<ctrl>+<alt>+r", "mode": "hold"},
            "whisper": {"model_size": "small", "language": "en"},
        }
        with open(config_path, "w") as f:
            yaml.dump(old_config, f)

        with patch.object(Config, "get_config_path", return_value=config_path):
            config = Config.load()

            # Paste hotkey should use defaults
            assert config.paste_hotkey.enabled is False
            assert config.paste_hotkey.combination == "<shift>+<mouse_middle>"
            assert config.paste_hotkey.mode == "hold"
            assert config.paste_hotkey.restore_clipboard is False  # Default changed

            # Existing settings should still load
            assert config.hotkey.combination == "<ctrl>+<alt>+r"

    def test_save_and_load_paste_hotkey(self, temp_config_dir: Path) -> None:
        """Paste hotkey config is saved and loaded correctly."""
        from elivroimagine.config import Config

        config_path = temp_config_dir / "config.yaml"

        with patch.object(Config, "get_config_path", return_value=config_path):
            config = Config()
            config.paste_hotkey.enabled = True
            config.paste_hotkey.combination = "<ctrl>+<mouse_middle>"
            config.paste_hotkey.mode = "toggle"
            config.paste_hotkey.restore_clipboard = False
            config.save()

            loaded = Config.load()
            assert loaded.paste_hotkey.enabled is True
            assert loaded.paste_hotkey.combination == "<ctrl>+<mouse_middle>"
            assert loaded.paste_hotkey.mode == "toggle"
            assert loaded.paste_hotkey.restore_clipboard is False


class TestTranscriptionConfig:
    """Test TranscriptionConfig defaults and persistence."""

    def test_default_values(self) -> None:
        """TranscriptionConfig has correct defaults."""
        from elivroimagine.config import TranscriptionConfig

        config = TranscriptionConfig()

        assert config.backend == "local"
        assert config.berget_api_key == ""

    def test_config_has_transcription(self) -> None:
        """Config includes transcription field with defaults."""
        from elivroimagine.config import Config

        config = Config()

        assert config.transcription.backend == "local"
        assert config.transcription.berget_api_key == ""

    def test_backward_compat_missing_section(self, temp_config_dir: Path) -> None:
        """Config without transcription section loads with defaults."""
        from elivroimagine.config import Config

        config_path = temp_config_dir / "config.yaml"

        # Old config without transcription section
        old_config = {
            "hotkey": {"combination": "<ctrl>+<alt>+r", "mode": "hold"},
            "whisper": {"model_size": "small", "language": "en"},
        }
        with open(config_path, "w") as f:
            yaml.dump(old_config, f)

        with patch.object(Config, "get_config_path", return_value=config_path):
            config = Config.load()

            # Transcription should use defaults
            assert config.transcription.backend == "local"
            assert config.transcription.berget_api_key == ""

            # Existing settings should still load
            assert config.hotkey.combination == "<ctrl>+<alt>+r"

    def test_save_and_load_transcription_config(self, temp_config_dir: Path) -> None:
        """Transcription config is saved and loaded correctly."""
        from elivroimagine.config import Config

        config_path = temp_config_dir / "config.yaml"

        with patch.object(Config, "get_config_path", return_value=config_path):
            config = Config()
            config.transcription.backend = "berget"
            config.transcription.berget_api_key = "test-api-key-123"
            config.save()

            loaded = Config.load()
            assert loaded.transcription.backend == "berget"
            assert loaded.transcription.berget_api_key == "test-api-key-123"

    def test_valid_backends_accepted(self) -> None:
        """Valid backend values are accepted."""
        from elivroimagine.config import TranscriptionConfig

        config = TranscriptionConfig(backend="local")
        assert config.backend == "local"

        config = TranscriptionConfig(backend="berget")
        assert config.backend == "berget"


class TestDevTrackerHotkeyConfig:
    """Test DevTrackerHotkeyConfig defaults and persistence."""

    def test_default_values(self) -> None:
        """DevTrackerHotkeyConfig has correct defaults."""
        from elivroimagine.config import DevTrackerHotkeyConfig

        config = DevTrackerHotkeyConfig()

        assert config.enabled is False
        assert config.combination == "<ctrl>+<alt>+i"
        assert config.scan_code is None
        assert config.mode == "hold"
        assert config.project == "intranet"

    def test_config_has_devtracker_hotkey(self) -> None:
        """Config includes devtracker_hotkey field with defaults."""
        from elivroimagine.config import Config

        config = Config()

        assert config.devtracker_hotkey.enabled is False
        assert config.devtracker_hotkey.combination == "<ctrl>+<alt>+i"
        assert config.devtracker_hotkey.project == "intranet"

    def test_backward_compat_missing_section(self, temp_config_dir: Path) -> None:
        """Config without devtracker_hotkey section loads with defaults."""
        from elivroimagine.config import Config

        config_path = temp_config_dir / "config.yaml"

        # Old config without devtracker_hotkey section
        old_config = {
            "hotkey": {"combination": "<ctrl>+<alt>+r", "mode": "hold"},
            "whisper": {"model_size": "small", "language": "en"},
            "devtracker": {"enabled": True, "api_key": "key", "email": "a@b.c", "project": "elivro"},
        }
        with open(config_path, "w") as f:
            yaml.dump(old_config, f)

        with patch.object(Config, "get_config_path", return_value=config_path):
            config = Config.load()

            # DevTracker hotkey should use defaults
            assert config.devtracker_hotkey.enabled is False
            assert config.devtracker_hotkey.combination == "<ctrl>+<alt>+i"
            assert config.devtracker_hotkey.mode == "hold"
            assert config.devtracker_hotkey.project == "intranet"

            # Existing settings should still load
            assert config.devtracker.enabled is True
            assert config.hotkey.combination == "<ctrl>+<alt>+r"

    def test_save_and_load_devtracker_hotkey(self, temp_config_dir: Path) -> None:
        """DevTracker hotkey config is saved and loaded correctly."""
        from elivroimagine.config import Config

        config_path = temp_config_dir / "config.yaml"

        with patch.object(Config, "get_config_path", return_value=config_path):
            config = Config()
            config.devtracker_hotkey.enabled = True
            config.devtracker_hotkey.combination = "<ctrl>+<alt>+p"
            config.devtracker_hotkey.scan_code = 25
            config.devtracker_hotkey.mode = "toggle"
            config.devtracker_hotkey.project = "my-project"
            config.save()

            loaded = Config.load()
            assert loaded.devtracker_hotkey.enabled is True
            assert loaded.devtracker_hotkey.combination == "<ctrl>+<alt>+p"
            assert loaded.devtracker_hotkey.scan_code == 25
            assert loaded.devtracker_hotkey.mode == "toggle"
            assert loaded.devtracker_hotkey.project == "my-project"

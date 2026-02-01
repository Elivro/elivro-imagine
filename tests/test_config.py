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

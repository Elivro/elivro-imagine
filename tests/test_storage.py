"""Tests for transcription storage management."""

from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest


class TestStorageManagerSave:
    """Test saving transcriptions."""

    def test_save_transcription_creates_file(self, temp_storage_dir: Path) -> None:
        """Saving transcription creates markdown file."""
        from elivroimagine.config import StorageConfig
        from elivroimagine.storage import StorageManager

        config = StorageConfig(transcriptions_dir=str(temp_storage_dir))
        storage = StorageManager(config)

        filepath = storage.save_transcription("Hello world", 5.5)

        assert filepath.exists()
        assert filepath.suffix == ".md"
        assert filepath.parent == temp_storage_dir

    def test_save_transcription_content_format(self, temp_storage_dir: Path) -> None:
        """Saved file has correct YAML frontmatter format."""
        from elivroimagine.config import StorageConfig
        from elivroimagine.storage import StorageManager

        config = StorageConfig(transcriptions_dir=str(temp_storage_dir))
        storage = StorageManager(config)

        filepath = storage.save_transcription("Test content", 10.0)

        content = filepath.read_text(encoding="utf-8")

        # Check frontmatter structure
        assert content.startswith("---\n")
        assert "timestamp:" in content
        assert "duration: 10.0s" in content
        assert "---\n\nTest content\n" in content

    def test_save_transcription_filename_format(self, temp_storage_dir: Path) -> None:
        """Saved file has timestamp-based filename."""
        from elivroimagine.config import StorageConfig
        from elivroimagine.storage import StorageManager

        config = StorageConfig(transcriptions_dir=str(temp_storage_dir))
        storage = StorageManager(config)

        fixed_time = datetime(2024, 3, 15, 14, 30, 45)
        with patch(
            "elivroimagine.storage.datetime"
        ) as mock_dt:
            mock_dt.now.return_value = fixed_time
            mock_dt.strftime = datetime.strftime

            filepath = storage.save_transcription("Test", 1.0)

            assert filepath.name == "2024-03-15_143045.md"


class TestStorageManagerGet:
    """Test retrieving transcriptions."""

    def test_get_transcriptions_empty(self, temp_storage_dir: Path) -> None:
        """Getting transcriptions from empty dir returns empty list."""
        from elivroimagine.config import StorageConfig
        from elivroimagine.storage import StorageManager

        config = StorageConfig(transcriptions_dir=str(temp_storage_dir))
        storage = StorageManager(config)

        files = storage.get_transcriptions()

        assert files == []

    def test_get_transcriptions_returns_md_files(
        self, temp_storage_dir: Path
    ) -> None:
        """Getting transcriptions returns only .md files."""
        from elivroimagine.config import StorageConfig
        from elivroimagine.storage import StorageManager

        config = StorageConfig(transcriptions_dir=str(temp_storage_dir))
        storage = StorageManager(config)

        # Create some files
        (temp_storage_dir / "test1.md").write_text("content1")
        (temp_storage_dir / "test2.md").write_text("content2")
        (temp_storage_dir / "other.txt").write_text("not markdown")

        files = storage.get_transcriptions()

        assert len(files) == 2
        assert all(f.suffix == ".md" for f in files)

    def test_get_transcriptions_sorted_newest_first(
        self, temp_storage_dir: Path
    ) -> None:
        """Transcriptions are sorted by name, newest first."""
        from elivroimagine.config import StorageConfig
        from elivroimagine.storage import StorageManager

        config = StorageConfig(transcriptions_dir=str(temp_storage_dir))
        storage = StorageManager(config)

        # Create files with date-based names
        (temp_storage_dir / "2024-01-01_120000.md").write_text("old")
        (temp_storage_dir / "2024-03-15_120000.md").write_text("new")
        (temp_storage_dir / "2024-02-10_120000.md").write_text("mid")

        files = storage.get_transcriptions()

        assert files[0].name == "2024-03-15_120000.md"
        assert files[1].name == "2024-02-10_120000.md"
        assert files[2].name == "2024-01-01_120000.md"

    def test_get_transcriptions_excludes_archive(
        self, temp_storage_dir: Path
    ) -> None:
        """Archive folder files are not included in transcriptions."""
        from elivroimagine.config import StorageConfig
        from elivroimagine.storage import StorageManager

        config = StorageConfig(transcriptions_dir=str(temp_storage_dir))
        storage = StorageManager(config)

        # Create files in main and archive (archive already created by StorageManager)
        (temp_storage_dir / "active.md").write_text("active")
        archive_dir = temp_storage_dir / "archive"
        # archive_dir already exists from StorageManager init
        (archive_dir / "archived.md").write_text("archived")

        files = storage.get_transcriptions()

        assert len(files) == 1
        assert files[0].name == "active.md"


class TestStorageManagerArchive:
    """Test archiving transcriptions."""

    def test_archive_transcription_moves_file(self, temp_storage_dir: Path) -> None:
        """Archiving moves file to archive folder."""
        from elivroimagine.config import StorageConfig
        from elivroimagine.storage import StorageManager

        config = StorageConfig(transcriptions_dir=str(temp_storage_dir))
        storage = StorageManager(config)

        # Create a transcription
        original = temp_storage_dir / "test.md"
        original.write_text("content")

        archive_path = storage.archive_transcription(original)

        assert not original.exists()
        assert archive_path.exists()
        assert archive_path.parent.name == "archive"
        assert archive_path.read_text() == "content"

    def test_archive_all_moves_all_files(self, temp_storage_dir: Path) -> None:
        """Archive all moves all transcriptions to archive."""
        from elivroimagine.config import StorageConfig
        from elivroimagine.storage import StorageManager

        config = StorageConfig(transcriptions_dir=str(temp_storage_dir))
        storage = StorageManager(config)

        # Create multiple transcriptions
        (temp_storage_dir / "file1.md").write_text("content1")
        (temp_storage_dir / "file2.md").write_text("content2")
        (temp_storage_dir / "file3.md").write_text("content3")

        archived = storage.archive_all()

        assert len(archived) == 3
        assert storage.get_transcriptions() == []
        assert all(p.parent.name == "archive" for p in archived)


class TestStorageManagerDirectories:
    """Test directory management."""

    def test_ensures_directories_on_init(self, temp_storage_dir: Path) -> None:
        """StorageManager creates directories on initialization."""
        from elivroimagine.config import StorageConfig
        from elivroimagine.storage import StorageManager

        # Use subdirectory that doesn't exist yet
        new_dir = temp_storage_dir / "new_transcriptions"
        config = StorageConfig(transcriptions_dir=str(new_dir))

        storage = StorageManager(config)

        assert new_dir.exists()
        assert (new_dir / "archive").exists()

    def test_get_transcriptions_folder(self, temp_storage_dir: Path) -> None:
        """get_transcriptions_folder returns correct path."""
        from elivroimagine.config import StorageConfig
        from elivroimagine.storage import StorageManager

        config = StorageConfig(transcriptions_dir=str(temp_storage_dir))
        storage = StorageManager(config)

        assert storage.get_transcriptions_folder() == temp_storage_dir

    def test_update_config_creates_new_directories(
        self, temp_storage_dir: Path
    ) -> None:
        """Updating config creates directories for new path."""
        from elivroimagine.config import StorageConfig
        from elivroimagine.storage import StorageManager

        config = StorageConfig(transcriptions_dir=str(temp_storage_dir))
        storage = StorageManager(config)

        new_dir = temp_storage_dir / "new_location"
        new_config = StorageConfig(transcriptions_dir=str(new_dir))
        storage.update_config(new_config)

        assert new_dir.exists()
        assert (new_dir / "archive").exists()

"""Storage management for transcriptions."""

import logging
import shutil
from datetime import datetime
from pathlib import Path

from .config import StorageConfig
from .utils import check_disk_space

logger = logging.getLogger(__name__)


class InsufficientDiskSpaceError(Exception):
    """Raised when there is not enough disk space to save a transcription."""

    pass


class StorageManager:
    """Manages transcription file storage."""

    def __init__(self, config: StorageConfig) -> None:
        self.config = config
        self._ensure_directories()

    def _ensure_directories(self) -> None:
        """Create necessary directories."""
        self.config.transcriptions_path.mkdir(parents=True, exist_ok=True)
        self.config.archive_path.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Storage directories verified: {self.config.transcriptions_path}")

    def save_transcription(self, text: str, duration: float) -> Path:
        """Save transcription to a markdown file.

        Args:
            text: Transcribed text.
            duration: Recording duration in seconds.

        Returns:
            Path to the saved file.

        Raises:
            InsufficientDiskSpaceError: If disk space is below threshold.
        """
        # Check disk space before writing
        has_space, available_mb = check_disk_space(
            self.config.transcriptions_path, required_mb=10
        )
        if not has_space:
            logger.error(
                f"Insufficient disk space: {available_mb}MB available, need 10MB"
            )
            raise InsufficientDiskSpaceError(
                f"Only {available_mb}MB available. Need at least 10MB."
            )

        timestamp = datetime.now()
        filename = timestamp.strftime("%Y-%m-%d_%H%M%S.md")
        filepath = self.config.transcriptions_path / filename

        content = self._format_transcription(text, timestamp, duration)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

        logger.info(f"Saved transcription: {filepath.name} ({duration:.1f}s)")
        return filepath

    def _format_transcription(
        self,
        text: str,
        timestamp: datetime,
        duration: float,
    ) -> str:
        """Format transcription with YAML frontmatter.

        Args:
            text: Transcribed text.
            timestamp: Recording timestamp.
            duration: Recording duration in seconds.

        Returns:
            Formatted markdown content.
        """
        formatted_timestamp = timestamp.strftime("%Y-%m-%d %H:%M:%S")
        formatted_duration = f"{duration:.1f}s"

        return f"""---
timestamp: {formatted_timestamp}
duration: {formatted_duration}
---

{text}
"""

    def get_transcriptions(self) -> list[Path]:
        """Get list of transcription files (not archived).

        Returns:
            List of paths to transcription files, sorted by date (newest first).
        """
        files = list(self.config.transcriptions_path.glob("*.md"))
        return sorted(files, key=lambda p: p.name, reverse=True)

    def archive_transcription(self, filepath: Path) -> Path:
        """Move a transcription to the archive folder.

        Args:
            filepath: Path to the transcription file.

        Returns:
            New path in archive folder.

        Raises:
            FileNotFoundError: If the source file doesn't exist.
        """
        if not filepath.exists():
            raise FileNotFoundError(f"File not found: {filepath}")

        archive_path = self.config.archive_path / filepath.name

        # Handle name collisions
        if archive_path.exists():
            stem = filepath.stem
            suffix = filepath.suffix
            counter = 1
            while archive_path.exists():
                archive_path = self.config.archive_path / f"{stem}_{counter}{suffix}"
                counter += 1

        shutil.move(str(filepath), str(archive_path))
        logger.info(f"Archived transcription: {filepath.name}")
        return archive_path

    def archive_all(self) -> list[Path]:
        """Archive all transcriptions.

        Returns:
            List of archived file paths.
        """
        archived = []
        for filepath in self.get_transcriptions():
            archived.append(self.archive_transcription(filepath))
        logger.info(f"Archived {len(archived)} transcriptions")
        return archived

    def get_transcriptions_folder(self) -> Path:
        """Get the transcriptions folder path."""
        return self.config.transcriptions_path

    def update_config(self, config: StorageConfig) -> None:
        """Update storage configuration."""
        self.config = config
        self._ensure_directories()

"""Storage management for transcriptions."""

import shutil
from datetime import datetime
from pathlib import Path

from .config import StorageConfig


class StorageManager:
    """Manages transcription file storage."""

    def __init__(self, config: StorageConfig) -> None:
        self.config = config
        self._ensure_directories()

    def _ensure_directories(self) -> None:
        """Create necessary directories."""
        self.config.transcriptions_path.mkdir(parents=True, exist_ok=True)
        self.config.archive_path.mkdir(parents=True, exist_ok=True)

    def save_transcription(self, text: str, duration: float) -> Path:
        """Save transcription to a markdown file.

        Args:
            text: Transcribed text.
            duration: Recording duration in seconds.

        Returns:
            Path to the saved file.
        """
        timestamp = datetime.now()
        filename = timestamp.strftime("%Y-%m-%d_%H%M%S.md")
        filepath = self.config.transcriptions_path / filename

        content = self._format_transcription(text, timestamp, duration)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

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
        """
        archive_path = self.config.archive_path / filepath.name
        shutil.move(str(filepath), str(archive_path))
        return archive_path

    def archive_all(self) -> list[Path]:
        """Archive all transcriptions.

        Returns:
            List of archived file paths.
        """
        archived = []
        for filepath in self.get_transcriptions():
            archived.append(self.archive_transcription(filepath))
        return archived

    def get_transcriptions_folder(self) -> Path:
        """Get the transcriptions folder path."""
        return self.config.transcriptions_path

    def update_config(self, config: StorageConfig) -> None:
        """Update storage configuration."""
        self.config = config
        self._ensure_directories()

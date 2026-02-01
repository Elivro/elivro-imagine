"""System tray integration using pystray."""

import logging
import subprocess
import sys
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Callable

from PIL import Image, ImageDraw
from pystray import Icon, Menu, MenuItem

if TYPE_CHECKING:
    from .app import ElivroImagineApp

logger = logging.getLogger(__name__)


class SystemTray:
    """System tray icon with menu."""

    def __init__(
        self,
        on_settings: Callable[[], None],
        on_quit: Callable[[], None],
        transcriptions_folder: Path,
    ) -> None:
        """Initialize system tray.

        Args:
            on_settings: Callback when Settings is clicked.
            on_quit: Callback when Quit is clicked.
            transcriptions_folder: Path to transcriptions folder.
        """
        self.on_settings = on_settings
        self.on_quit = on_quit
        self.transcriptions_folder = transcriptions_folder

        self._icon: Icon | None = None
        self._recording = False
        self._icon_idle = self._create_icon("#4CAF50")  # Green
        self._icon_recording = self._create_icon("#F44336")  # Red

    def _create_icon(self, color: str) -> Image.Image:
        """Create a simple circular icon.

        Args:
            color: Hex color for the icon.

        Returns:
            PIL Image.
        """
        size = 64
        image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)

        # Draw filled circle
        margin = 4
        draw.ellipse(
            [margin, margin, size - margin, size - margin],
            fill=color,
            outline="#FFFFFF",
            width=2,
        )

        # Draw microphone symbol (simplified)
        mic_color = "#FFFFFF"
        center_x = size // 2
        center_y = size // 2

        # Microphone body
        draw.rectangle(
            [center_x - 6, center_y - 12, center_x + 6, center_y + 4],
            fill=mic_color,
        )
        # Microphone base
        draw.arc(
            [center_x - 10, center_y - 2, center_x + 10, center_y + 14],
            start=0,
            end=180,
            fill=mic_color,
            width=2,
        )
        # Stand
        draw.line(
            [center_x, center_y + 12, center_x, center_y + 18],
            fill=mic_color,
            width=2,
        )
        draw.line(
            [center_x - 6, center_y + 18, center_x + 6, center_y + 18],
            fill=mic_color,
            width=2,
        )

        return image

    def _open_transcriptions_folder(self) -> None:
        """Open transcriptions folder in file explorer."""
        folder = str(self.transcriptions_folder)
        if sys.platform == "win32":
            subprocess.Popen(["explorer", folder])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", folder])
        else:
            subprocess.Popen(["xdg-open", folder])

    def _create_menu(self) -> Menu:
        """Create the tray menu."""
        return Menu(
            MenuItem("ElivroImagine", None, enabled=False),
            Menu.SEPARATOR,
            MenuItem("Open Transcriptions", lambda: self._open_transcriptions_folder()),
            MenuItem("Settings", lambda: self.on_settings()),
            Menu.SEPARATOR,
            MenuItem("Quit", lambda: self._quit()),
        )

    def _quit(self) -> None:
        """Handle quit from menu."""
        self.on_quit()
        if self._icon:
            self._icon.stop()

    def start(self) -> None:
        """Start the system tray icon."""
        self._icon = Icon(
            "ElivroImagine",
            self._icon_idle,
            "ElivroImagine - Ready",
            menu=self._create_menu(),
        )

        # Run in separate thread
        thread = threading.Thread(target=self._icon.run, daemon=True)
        thread.start()

    def stop(self) -> None:
        """Stop the system tray icon."""
        if self._icon:
            self._icon.stop()
            self._icon = None

    def set_recording(self, recording: bool) -> None:
        """Update icon to show recording state.

        Args:
            recording: True if recording, False otherwise.
        """
        self._recording = recording
        if self._icon:
            if recording:
                self._icon.icon = self._icon_recording
                self._icon.title = "ElivroImagine - Recording..."
            else:
                self._icon.icon = self._icon_idle
                self._icon.title = "ElivroImagine - Ready"

    def notify(self, title: str, message: str) -> None:
        """Show a notification.

        Args:
            title: Notification title.
            message: Notification message.
        """
        if self._icon:
            self._icon.notify(message, title)

    def update_transcriptions_folder(self, folder: Path) -> None:
        """Update the transcriptions folder path."""
        self.transcriptions_folder = folder

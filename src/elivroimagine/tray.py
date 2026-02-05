"""System tray integration using pystray."""

import logging
import subprocess
import sys
import threading
from importlib import resources
from pathlib import Path
from typing import TYPE_CHECKING, Callable

from PIL import Image, ImageDraw
from pystray import Icon, Menu, MenuItem

if TYPE_CHECKING:
    from .app import ElivroImagineApp

logger = logging.getLogger(__name__)

# Icon size for tray (larger for better quality on high-DPI displays)
ICON_SIZE = 128


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
        self._transcribing = False
        self._base_icon = self._load_base_icon()
        self._icon_idle = self._base_icon.copy()
        self._icon_recording = self._create_status_icon("#F44336")  # Red
        self._icon_transcribing = self._create_status_icon("#FF9800")  # Orange

    def _load_base_icon(self) -> Image.Image:
        """Load the base icon from assets.

        Returns:
            PIL Image resized to tray icon size.
        """
        try:
            # Try to load from package assets
            assets_path = Path(__file__).parent / "assets" / "icon.png"
            if assets_path.exists():
                icon = Image.open(assets_path)
                icon = icon.convert("RGBA")

                # Create a white circular background for visibility
                background = Image.new("RGBA", (ICON_SIZE, ICON_SIZE), (0, 0, 0, 0))
                draw = ImageDraw.Draw(background)
                # Draw white circle as background
                margin = 2
                draw.ellipse(
                    [margin, margin, ICON_SIZE - margin, ICON_SIZE - margin],
                    fill="#FFFFFF",
                )

                # Resize logo to fit inside the circle, preserving aspect ratio
                available = ICON_SIZE - 24  # padding inside circle
                src_w, src_h = icon.size
                ratio = min(available / src_w, available / src_h)
                new_w = int(src_w * ratio)
                new_h = int(src_h * ratio)
                icon = icon.resize((new_w, new_h), Image.Resampling.LANCZOS)

                # Center the logo on the background
                ox = (ICON_SIZE - new_w) // 2
                oy = (ICON_SIZE - new_h) // 2
                background.paste(icon, (ox, oy), icon)

                return background
        except Exception as e:
            logger.warning(f"Failed to load icon from assets: {e}")

        # Fallback to simple generated icon
        return self._create_fallback_icon()

    def _create_fallback_icon(self) -> Image.Image:
        """Create a simple fallback icon if logo not found."""
        image = Image.new("RGBA", (ICON_SIZE, ICON_SIZE), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        margin = 4
        draw.ellipse(
            [margin, margin, ICON_SIZE - margin, ICON_SIZE - margin],
            fill="#FFFFFF",
            outline="#000000",
            width=2,
        )
        return image

    def _create_status_icon(self, badge_color: str) -> Image.Image:
        """Create an icon with a colored status badge.

        Args:
            badge_color: Hex color for the status badge.

        Returns:
            PIL Image with status badge overlay.
        """
        icon = self._base_icon.copy()
        draw = ImageDraw.Draw(icon)

        # Draw status badge in bottom-right corner
        badge_size = 20
        badge_x = ICON_SIZE - badge_size - 2
        badge_y = ICON_SIZE - badge_size - 2

        # Badge with white border
        draw.ellipse(
            [badge_x - 2, badge_y - 2, badge_x + badge_size + 2, badge_y + badge_size + 2],
            fill="#FFFFFF",
        )
        draw.ellipse(
            [badge_x, badge_y, badge_x + badge_size, badge_y + badge_size],
            fill=badge_color,
        )

        return icon

    def _open_transcriptions_folder(self) -> None:
        """Open transcriptions folder in file explorer."""
        folder = self.transcriptions_folder

        if not folder.exists():
            try:
                folder.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                logger.error(f"Failed to create folder: {e}")
                return

        try:
            if sys.platform == "win32":
                subprocess.Popen(["explorer", str(folder)])
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(folder)])
            else:
                subprocess.Popen(["xdg-open", str(folder)])
        except Exception as e:
            logger.error(f"Failed to open folder: {e}")

    def _create_menu(self) -> Menu:
        """Create the tray menu."""
        return Menu(
            MenuItem("ElivroImagine", None, enabled=False),
            Menu.SEPARATOR,
            MenuItem("Open Transcriptions", lambda: self._open_transcriptions_folder()),
            MenuItem("Settings", lambda: self.on_settings(), default=True),
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
            elif self._transcribing:
                self._icon.icon = self._icon_transcribing
                self._icon.title = "ElivroImagine - Transcribing..."
            else:
                self._icon.icon = self._icon_idle
                self._icon.title = "ElivroImagine - Ready"

    def set_transcribing(self, transcribing: bool) -> None:
        """Update icon to show transcription in progress.

        Args:
            transcribing: True if transcribing, False otherwise.
        """
        self._transcribing = transcribing
        if self._icon and not self._recording:
            if transcribing:
                self._icon.icon = self._icon_transcribing
                self._icon.title = "ElivroImagine - Transcribing..."
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

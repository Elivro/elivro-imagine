"""Epic cooking-themed splash screen for ElivroImagine."""

import random
import sys
import threading
import tkinter as tk
from pathlib import Path
from typing import Callable

from PIL import Image, ImageDraw, ImageTk

from . import __version__


class SplashScreen:
    """Epic cooking-themed splash screen shown during app startup."""

    # Over-the-top cooking-themed loading messages
    COOKING_MESSAGES = [
        "Preheating the neural oven...",
        "Whisking up some AI magic...",
        "Marinating your brilliance...",
        "Simmering the transcription sauce...",
        "Adding a pinch of genius...",
        "Letting the ideas rise...",
        "Caramelizing your thoughts...",
        "Plating up something extraordinary...",
        "Chef's kiss incoming...",
        "This is gonna be LEGENDARY...",
        "Cooking up pure gold...",
        "Seasoning with awesomeness...",
        "The secret ingredient? YOU.",
        "About to serve absolute fire...",
        "Gordon Ramsay would be proud...",
        "Mise en place for magnificence...",
        "Flambéing the algorithms...",
        "Reducing complexity to perfection...",
        "Taste-testing the transcriptions...",
        "Garnishing with genius...",
        "The kitchen is getting HOT...",
        "Preparing a masterpiece...",
        "Five-star quality incoming...",
        "Your ideas are on the menu...",
    ]

    # Window dimensions
    WIDTH = 420
    HEIGHT = 320

    # Brand colors - clean white/black theme
    ACCENT_COLOR = "#000000"
    BG_COLOR = "#ffffff"
    TEXT_COLOR = "#000000"
    SUBTEXT_COLOR = "#666666"

    def __init__(self) -> None:
        """Initialize splash screen."""
        self._root: tk.Tk | None = None
        self._message_var: tk.StringVar | None = None
        self._message_index = 0
        self._rotation_job: str | None = None
        self._animation_job: str | None = None
        self._logo_photo: ImageTk.PhotoImage | None = None
        self._closed = False
        self._lock = threading.Lock()
        self._progress_percent = 0  # 0-100, 0 means indeterminate mode
        self._progress_canvas: tk.Canvas | None = None

    def show(self) -> None:
        """Show the splash screen.

        Must be called from the main thread before tkinter mainloop starts.
        """
        self._root = tk.Tk()
        self._root.title("ElivroImagine")
        self._root.overrideredirect(True)  # Borderless window
        self._root.configure(bg=self.BG_COLOR)

        # Center on screen
        screen_width = self._root.winfo_screenwidth()
        screen_height = self._root.winfo_screenheight()
        x = (screen_width - self.WIDTH) // 2
        y = (screen_height - self.HEIGHT) // 2
        self._root.geometry(f"{self.WIDTH}x{self.HEIGHT}+{x}+{y}")

        # Keep on top
        self._root.attributes("-topmost", True)

        # Subtle border
        self._root.configure(highlightthickness=1, highlightbackground="#e0e0e0")

        # Apply rounded corners on Windows (DWM rounded-lg style)
        self._apply_rounded_corners()

        # Build UI
        self._build_ui()

        # Start message rotation
        self._rotate_message()

        # Process events to show the window
        self._root.update()

    def _apply_rounded_corners(self) -> None:
        """Apply rounded corners to the splash window on Windows.

        Uses the DWM DWMWA_WINDOW_CORNER_PREFERENCE attribute (Windows 11+)
        with DWMWCP_ROUND = 2 for standard rounding (~8px, like rounded-lg).
        """
        if sys.platform != "win32" or self._root is None:
            return

        try:
            import ctypes
            from ctypes import wintypes

            # DWMWA_WINDOW_CORNER_PREFERENCE = 33
            # DWMWCP_ROUND = 2 (standard rounded corners ~8px)
            DWMWA_WINDOW_CORNER_PREFERENCE = 33
            DWMWCP_ROUND = 2

            dwmapi = ctypes.windll.dwmapi
            self._root.update_idletasks()
            hwnd = ctypes.windll.user32.GetParent(self._root.winfo_id())
            value = ctypes.c_int(DWMWCP_ROUND)
            dwmapi.DwmSetWindowAttribute(
                hwnd,
                DWMWA_WINDOW_CORNER_PREFERENCE,
                ctypes.byref(value),
                ctypes.sizeof(value),
            )
        except Exception:
            pass  # Silently fail on older Windows versions

    def _build_ui(self) -> None:
        """Build the splash screen UI."""
        if self._root is None:
            return

        # Main container with padding
        container = tk.Frame(self._root, bg=self.BG_COLOR)
        container.pack(expand=True, fill="both", padx=20, pady=20)

        # Logo
        self._load_and_show_logo(container)

        # App name with epic styling
        title_frame = tk.Frame(container, bg=self.BG_COLOR)
        title_frame.pack(pady=(10, 5))

        title_label = tk.Label(
            title_frame,
            text="ElivroImagine",
            font=("Segoe UI", 24, "bold"),
            fg=self.ACCENT_COLOR,
            bg=self.BG_COLOR,
        )
        title_label.pack()

        # Tagline
        tagline = tk.Label(
            container,
            text="Voice-to-Backlog Magic",
            font=("Segoe UI", 11, "italic"),
            fg=self.SUBTEXT_COLOR,
            bg=self.BG_COLOR,
        )
        tagline.pack(pady=(0, 15))

        # Progress bar (indeterminate)
        style = tk.ttk.Style() if hasattr(tk, "ttk") else None
        progress_frame = tk.Frame(container, bg=self.BG_COLOR)
        progress_frame.pack(fill="x", pady=(0, 15))

        # Simple animated bar using canvas
        self._progress_canvas = tk.Canvas(
            progress_frame,
            height=4,
            bg="#e0e0e0",
            highlightthickness=0,
        )
        self._progress_canvas.pack(fill="x")
        self._animate_progress()

        # Rotating message
        self._message_var = tk.StringVar(value=random.choice(self.COOKING_MESSAGES))
        message_label = tk.Label(
            container,
            textvariable=self._message_var,
            font=("Segoe UI", 12),
            fg=self.TEXT_COLOR,
            bg=self.BG_COLOR,
        )
        message_label.pack(pady=(0, 20))

        # Version
        version_label = tk.Label(
            container,
            text=f"v{__version__}",
            font=("Segoe UI", 9),
            fg=self.SUBTEXT_COLOR,
            bg=self.BG_COLOR,
        )
        version_label.pack(side="bottom")

    def _load_and_show_logo(self, parent: tk.Frame) -> None:
        """Load and display the app logo with white circle background."""
        try:
            icon_path = Path(__file__).parent / "assets" / "icon.png"
            if icon_path.exists():
                icon = Image.open(icon_path).convert("RGBA")

                # Create white circular background (matching tray icon style)
                logo_size = 100
                background = Image.new("RGBA", (logo_size, logo_size), (0, 0, 0, 0))
                draw = ImageDraw.Draw(background)
                margin = 2
                draw.ellipse(
                    [margin, margin, logo_size - margin, logo_size - margin],
                    fill="#FFFFFF",
                )

                # Resize logo to fit inside the circle with padding
                inner_size = logo_size - 12
                icon = icon.resize((inner_size, inner_size), Image.Resampling.LANCZOS)
                offset = (logo_size - inner_size) // 2
                background.paste(icon, (offset, offset), icon)

                self._logo_photo = ImageTk.PhotoImage(background)

                logo_label = tk.Label(
                    parent,
                    image=self._logo_photo,
                    bg=self.BG_COLOR,
                )
                logo_label.pack(pady=(10, 0))
            else:
                self._show_fallback_logo(parent)
        except Exception:
            self._show_fallback_logo(parent)

    def _show_fallback_logo(self, parent: tk.Frame) -> None:
        """Show fallback logo when image can't be loaded."""
        emoji_label = tk.Label(
            parent,
            text="🎙️",
            font=("Segoe UI Emoji", 48),
            bg=self.BG_COLOR,
        )
        emoji_label.pack(pady=(10, 0))

    def _animate_progress(self) -> None:
        """Animate the progress bar (indeterminate mode) or draw determinate bar."""
        if self._closed or self._root is None or self._progress_canvas is None:
            return

        canvas = self._progress_canvas
        width = canvas.winfo_width() or self.WIDTH - 40

        # Clear and redraw
        canvas.delete("progress")

        if self._progress_percent > 0:
            # Determinate mode - fill based on percentage
            fill_width = int((self._progress_percent / 100) * width)
            canvas.create_rectangle(
                0, 0, fill_width, 6,
                fill=self.ACCENT_COLOR,
                tags="progress",
            )
            # Don't schedule animation in determinate mode
            return

        # Indeterminate mode - moving highlight effect
        if not hasattr(self, "_progress_pos"):
            self._progress_pos = 0

        bar_width = 80
        x1 = self._progress_pos
        x2 = x1 + bar_width

        canvas.create_rectangle(
            x1, 0, x2, 6,
            fill=self.ACCENT_COLOR,
            tags="progress",
        )

        # Move position
        self._progress_pos += 5
        if self._progress_pos > width:
            self._progress_pos = -bar_width

        # Schedule next frame
        if not self._closed:
            self._animation_job = self._root.after(30, self._animate_progress)

    def _rotate_message(self) -> None:
        """Rotate to the next cooking message."""
        if self._closed or self._root is None or self._message_var is None:
            return

        # Pick a random message (but not the same one)
        current = self._message_var.get()
        messages = [m for m in self.COOKING_MESSAGES if m != current]
        self._message_var.set(random.choice(messages))

        # Schedule next rotation (every 2 seconds)
        self._rotation_job = self._root.after(2000, self._rotate_message)

    def update_message(self, message: str | None = None) -> None:
        """Update the progress message.

        Thread-safe method to update the displayed message.

        Args:
            message: Custom message to show. If None, rotates to next
                     cooking message automatically.
        """
        with self._lock:
            if self._closed or self._root is None or self._message_var is None:
                return

        if message:
            # Thread-safe update via after() - wrap for thread safety
            try:
                self._root.after(0, lambda: self._set_message(message))
            except RuntimeError:
                pass  # Called from wrong thread - ignore
        # If no message, the automatic rotation handles it

    def _set_message(self, message: str) -> None:
        """Set message (must be called from main thread)."""
        if self._message_var and not self._closed:
            self._message_var.set(message)

    def set_progress(self, percent: int) -> None:
        """Set determinate progress percentage.

        Thread-safe method to set progress bar to a specific percentage.

        Args:
            percent: Progress percentage (0-100). Values > 0 switch to
                     determinate mode. 0 returns to indeterminate mode.
        """
        # Always update internal state
        self._progress_percent = max(0, min(100, percent))

        with self._lock:
            if self._closed or self._root is None:
                return

        # Redraw - wrap in try/except for thread safety
        try:
            self._root.after(0, self._animate_progress)
        except RuntimeError:
            # Called from wrong thread - ignore, animation will update naturally
            pass

    def update(self) -> None:
        """Process pending UI events.

        Call this periodically during initialization to keep the splash
        responsive.
        """
        with self._lock:
            if self._closed or self._root is None:
                return

        try:
            self._root.update()
        except tk.TclError:
            pass  # Window was destroyed

    def close(self) -> None:
        """Close the splash screen."""
        with self._lock:
            if self._closed:
                return
            self._closed = True

        if self._root is None:
            return

        try:
            # Cancel scheduled jobs
            if self._rotation_job:
                self._root.after_cancel(self._rotation_job)
                self._rotation_job = None
            if self._animation_job:
                self._root.after_cancel(self._animation_job)
                self._animation_job = None

            # Destroy window
            self._root.destroy()
            self._root = None
        except tk.TclError:
            pass  # Already destroyed


def create_splash() -> SplashScreen:
    """Create and show splash screen.

    Convenience function for creating a splash screen.

    Returns:
        The splash screen instance (call .close() when done).
    """
    splash = SplashScreen()
    splash.show()
    return splash

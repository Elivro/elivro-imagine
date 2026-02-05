"""Tests for splash screen module."""

import threading
import time
from unittest.mock import MagicMock, patch

import pytest


def _display_available() -> bool:
    """Check if display is available for GUI tests."""
    try:
        import tkinter as tk

        # Try to create a minimal Tk window
        root = tk.Tk()
        # If we get here, check if it's functional
        _ = root.winfo_screenwidth()
        root.withdraw()
        root.destroy()
        return True
    except Exception:
        return False


# Cache result at module load time
_DISPLAY_AVAILABLE = _display_available()


class TestSplashScreen:
    """Tests for SplashScreen class."""

    def test_cooking_messages_not_empty(self) -> None:
        """Verify cooking messages list is populated."""
        from elivroimagine.splash import SplashScreen

        assert len(SplashScreen.COOKING_MESSAGES) > 10
        for msg in SplashScreen.COOKING_MESSAGES:
            assert isinstance(msg, str)
            assert len(msg) > 5

    def test_cooking_messages_unique(self) -> None:
        """Verify all cooking messages are unique."""
        from elivroimagine.splash import SplashScreen

        messages = SplashScreen.COOKING_MESSAGES
        assert len(messages) == len(set(messages))

    def test_init_state(self) -> None:
        """Test initial state of SplashScreen."""
        from elivroimagine.splash import SplashScreen

        splash = SplashScreen()
        assert splash._root is None
        assert splash._message_var is None
        assert splash._closed is False
        assert splash._progress_percent == 0

    def test_set_progress_without_show(self) -> None:
        """Test set_progress before showing doesn't error."""
        from elivroimagine.splash import SplashScreen

        splash = SplashScreen()
        splash.set_progress(50)  # Should not raise
        assert splash._progress_percent == 50

    def test_set_progress_clamps_values(self) -> None:
        """Test set_progress clamps to 0-100 range."""
        from elivroimagine.splash import SplashScreen

        splash = SplashScreen()
        splash.set_progress(-10)
        assert splash._progress_percent == 0
        splash.set_progress(150)
        assert splash._progress_percent == 100

    def test_close_without_show(self) -> None:
        """Test closing splash before showing doesn't error."""
        from elivroimagine.splash import SplashScreen

        splash = SplashScreen()
        splash.close()  # Should not raise
        assert splash._closed is True

    def test_update_message_without_show(self) -> None:
        """Test update_message before showing doesn't error."""
        from elivroimagine.splash import SplashScreen

        splash = SplashScreen()
        splash.update_message("Test")  # Should not raise

    def test_update_without_show(self) -> None:
        """Test update() before showing doesn't error."""
        from elivroimagine.splash import SplashScreen

        splash = SplashScreen()
        splash.update()  # Should not raise

    def test_double_close(self) -> None:
        """Test closing splash twice doesn't error."""
        from elivroimagine.splash import SplashScreen

        splash = SplashScreen()
        splash.close()
        splash.close()  # Should not raise

    @pytest.mark.skipif(
        not _DISPLAY_AVAILABLE,
        reason="No display available for GUI tests",
    )
    def test_show_and_close(self) -> None:
        """Test showing and closing splash screen."""
        from elivroimagine.splash import SplashScreen

        splash = SplashScreen()
        splash.show()

        assert splash._root is not None
        assert splash._message_var is not None
        assert splash._closed is False

        # Verify message is one of the cooking messages
        current_msg = splash._message_var.get()
        assert current_msg in SplashScreen.COOKING_MESSAGES

        splash.close()
        assert splash._closed is True


class TestCreateSplash:
    """Tests for create_splash convenience function."""

    def test_returns_splash_screen(self) -> None:
        """Test create_splash returns SplashScreen instance."""
        from elivroimagine.splash import SplashScreen, create_splash

        # Mock show to avoid GUI
        with patch.object(SplashScreen, "show"):
            splash = create_splash()
            assert isinstance(splash, SplashScreen)
            splash.close()

"""Tests for Windows integration module."""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest


# Skip all tests if not on Windows
pytestmark = pytest.mark.skipif(
    sys.platform != "win32",
    reason="Windows-only tests"
)


class TestWindowsStartupManager:
    """Tests for WindowsStartupManager."""

    def test_get_pythonw_path_returns_valid_path(self) -> None:
        """_get_pythonw_path should return a valid Python path."""
        from elivroimagine.windows import WindowsStartupManager

        manager = WindowsStartupManager()
        path = manager._get_pythonw_path()

        assert path.endswith(".exe")
        assert "python" in path.lower()

    def test_get_launch_command_contains_module(self) -> None:
        """_get_launch_command should contain -m elivroimagine."""
        from elivroimagine.windows import WindowsStartupManager

        manager = WindowsStartupManager()
        command = manager._get_launch_command()

        assert "-m elivroimagine" in command

    def test_is_autostart_enabled_returns_bool(self) -> None:
        """is_autostart_enabled should return a boolean."""
        from elivroimagine.windows import WindowsStartupManager

        manager = WindowsStartupManager()
        result = manager.is_autostart_enabled()

        assert isinstance(result, bool)

    def test_enable_disable_autostart_roundtrip(self) -> None:
        """enable_autostart and disable_autostart should work together."""
        from elivroimagine.windows import WindowsStartupManager

        manager = WindowsStartupManager()

        # Store initial state
        initial_state = manager.is_autostart_enabled()

        try:
            # Enable autostart
            enable_result = manager.enable_autostart()
            assert enable_result is True
            assert manager.is_autostart_enabled() is True

            # Disable autostart
            disable_result = manager.disable_autostart()
            assert disable_result is True
            assert manager.is_autostart_enabled() is False
        finally:
            # Restore initial state
            if initial_state:
                manager.enable_autostart()
            else:
                manager.disable_autostart()

    def test_disable_autostart_succeeds_when_not_enabled(self) -> None:
        """disable_autostart should succeed even if not enabled."""
        from elivroimagine.windows import WindowsStartupManager

        manager = WindowsStartupManager()

        # First make sure it's disabled
        manager.disable_autostart()

        # Disabling again should still return True
        result = manager.disable_autostart()
        assert result is True


class TestStartMenuShortcut:
    """Tests for Start Menu shortcut creation."""

    def test_create_start_menu_shortcut_requires_pywin32(self) -> None:
        """create_start_menu_shortcut should handle missing pywin32."""
        # This test just verifies the method doesn't crash
        from elivroimagine.windows import WindowsStartupManager

        manager = WindowsStartupManager()
        result = manager.create_start_menu_shortcut()

        # Result depends on whether pywin32 is installed
        assert isinstance(result, bool)

    @patch.dict(os.environ, {"APPDATA": ""})
    def test_create_start_menu_shortcut_no_appdata(self) -> None:
        """create_start_menu_shortcut should fail gracefully without APPDATA."""
        from elivroimagine.windows import WindowsStartupManager

        manager = WindowsStartupManager()
        result = manager.create_start_menu_shortcut()

        assert result is False


class TestConstants:
    """Tests for module constants."""

    def test_registry_key_is_correct(self) -> None:
        """REGISTRY_KEY should point to Run key."""
        from elivroimagine.windows import REGISTRY_KEY

        assert "Run" in REGISTRY_KEY
        assert "CurrentVersion" in REGISTRY_KEY

    def test_app_name_is_set(self) -> None:
        """APP_NAME should be ElivroImagine."""
        from elivroimagine.windows import APP_NAME

        assert APP_NAME == "ElivroImagine"

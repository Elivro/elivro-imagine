"""Windows autostart and Start Menu integration for ElivroImagine."""

import logging
import os
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

# Registry path for Windows autostart
REGISTRY_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_NAME = "ElivroImagine"


class WindowsStartupManager:
    """Manages Windows startup and Start Menu integration."""

    def enable_autostart(self) -> bool:
        """Add registry entry to HKCU\\...\\Run for autostart.

        Returns:
            True if successful, False otherwise.
        """
        if sys.platform != "win32":
            logger.warning("enable_autostart called on non-Windows platform")
            return False

        try:
            import winreg

            # Use pythonw for no console window
            command = self._get_launch_command()
            key = None

            try:
                key = winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER,
                    REGISTRY_KEY,
                    0,
                    winreg.KEY_SET_VALUE,
                )
                winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, command)
                logger.info(f"Added autostart registry entry: {command}")
                return True
            finally:
                if key is not None:
                    winreg.CloseKey(key)

        except Exception as e:
            logger.error(f"Failed to enable autostart: {e}")
            return False

    def disable_autostart(self) -> bool:
        """Remove registry entry for autostart.

        Returns:
            True if successful or entry doesn't exist, False on error.
        """
        if sys.platform != "win32":
            logger.warning("disable_autostart called on non-Windows platform")
            return False

        try:
            import winreg

            key = None
            try:
                key = winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER,
                    REGISTRY_KEY,
                    0,
                    winreg.KEY_SET_VALUE,
                )
                try:
                    winreg.DeleteValue(key, APP_NAME)
                    logger.info("Removed autostart registry entry")
                except FileNotFoundError:
                    # Entry doesn't exist, that's fine
                    logger.debug("Autostart entry not found, nothing to remove")
                return True
            finally:
                if key is not None:
                    winreg.CloseKey(key)

        except Exception as e:
            logger.error(f"Failed to disable autostart: {e}")
            return False

    def is_autostart_enabled(self) -> bool:
        """Check if autostart is currently enabled.

        Returns:
            True if autostart is enabled, False otherwise.
        """
        if sys.platform != "win32":
            return False

        try:
            import winreg

            key = None
            try:
                key = winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER,
                    REGISTRY_KEY,
                    0,
                    winreg.KEY_READ,
                )
                try:
                    winreg.QueryValueEx(key, APP_NAME)
                    return True
                except FileNotFoundError:
                    return False
            finally:
                if key is not None:
                    winreg.CloseKey(key)

        except Exception as e:
            logger.debug(f"Failed to check autostart status: {e}")
            return False

    def create_start_menu_shortcut(self) -> bool:
        """Create a Start Menu shortcut for the application.

        Creates .lnk in %APPDATA%\\Microsoft\\Windows\\Start Menu\\Programs\\

        Returns:
            True if successful, False otherwise.
        """
        if sys.platform != "win32":
            logger.warning("create_start_menu_shortcut called on non-Windows platform")
            return False

        try:
            # Import Windows COM library
            import pythoncom
            from win32com.client import Dispatch

            pythoncom.CoInitialize()
            try:
                # Get Start Menu path
                appdata = os.environ.get("APPDATA", "")
                if not appdata:
                    logger.error("APPDATA environment variable not found")
                    return False

                start_menu_path = (
                    Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs"
                )
                shortcut_path = start_menu_path / f"{APP_NAME}.lnk"

                # Create shortcut
                shell = Dispatch("WScript.Shell")
                shortcut = shell.CreateShortCut(str(shortcut_path))
                shortcut.Targetpath = self._get_pythonw_path()
                shortcut.Arguments = "-m elivroimagine"
                shortcut.WorkingDirectory = str(Path.home())
                shortcut.Description = "ElivroImagine - Voice to Backlog"

                # Set icon
                icon_path = self._get_icon_path()
                if icon_path:
                    shortcut.IconLocation = f"{icon_path},0"

                shortcut.save()

                logger.info(f"Created Start Menu shortcut: {shortcut_path}")
                return True
            finally:
                pythoncom.CoUninitialize()

        except ImportError:
            logger.error("pywin32 not installed - cannot create shortcut")
            return False
        except Exception as e:
            logger.error(f"Failed to create Start Menu shortcut: {e}")
            return False

    def _get_pythonw_path(self) -> str:
        """Get the path to pythonw.exe (no console window).

        Returns:
            Path to pythonw.exe.
        """
        # Get the directory containing the current Python executable
        python_dir = Path(sys.executable).parent
        pythonw = python_dir / "pythonw.exe"

        if pythonw.exists():
            return str(pythonw)

        # Fallback to sys.executable directory
        return str(python_dir / "python.exe")

    def _get_launch_command(self) -> str:
        """Get the command to launch the application without console.

        Returns:
            Command string for launching the app.
        """
        pythonw = self._get_pythonw_path()
        return f'"{pythonw}" -m elivroimagine'

    def _get_icon_path(self) -> str | None:
        """Get the path to the application icon.

        Returns:
            Path to icon.ico or None if not found.
        """
        # Try package assets folder
        icon_path = Path(__file__).parent / "assets" / "icon.ico"
        if icon_path.exists():
            return str(icon_path)
        return None

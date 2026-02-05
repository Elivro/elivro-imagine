"""Entry point for ElivroImagine."""

import argparse
import sys

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .splash import SplashScreen


def _set_windows_app_id() -> None:
    """Set Windows App User Model ID for proper taskbar/notification identity."""
    if sys.platform != "win32":
        return

    try:
        import ctypes

        # Set App User Model ID so Windows identifies this as ElivroImagine
        # not as "Python"
        app_id = "Elivro.ElivroImagine.VoiceToBacklog.1"
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
    except Exception:
        pass  # Non-critical, continue without custom app ID


def main() -> int:
    """Main entry point."""
    # Set Windows app identity early
    _set_windows_app_id()
    parser = argparse.ArgumentParser(
        description="ElivroImagine - Voice to Backlog tool"
    )
    parser.add_argument(
        "--install",
        action="store_true",
        help="Create Start Menu shortcut and exit",
    )

    args = parser.parse_args()

    if args.install:
        if sys.platform != "win32":
            print("--install is only supported on Windows")
            return 1

        from .windows_integration import WindowsStartupManager

        manager = WindowsStartupManager()
        if manager.create_start_menu_shortcut():
            print("Start Menu shortcut created successfully")
            print("You can now find ElivroImagine in the Start Menu")
            return 0
        else:
            print("Failed to create Start Menu shortcut")
            print("Make sure pywin32 is installed: pip install pywin32")
            return 1

    # Show splash screen early (before heavy imports)
    from .splash import SplashScreen

    splash: SplashScreen | None = SplashScreen()
    splash.show()

    from .app import ElivroImagineApp

    app = ElivroImagineApp(splash=splash)
    app.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())

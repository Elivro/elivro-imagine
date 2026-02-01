"""Entry point for ElivroImagine."""

import sys


def main() -> int:
    """Main entry point."""
    from .app import ElivroImagineApp

    app = ElivroImagineApp()
    app.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())

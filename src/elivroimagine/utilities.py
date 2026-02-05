"""Production utilities for ElivroImagine."""

import logging
import os
import shutil
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


class SingleInstanceLock:
    """File-based single instance lock using Windows-friendly mechanism."""

    def __init__(self, lock_file: Path) -> None:
        self._lock_file = lock_file
        self._lock_handle: object | None = None

    def acquire(self) -> bool:
        """Acquire the instance lock.

        Returns:
            True if lock acquired, False if another instance is running.
        """
        try:
            self._lock_file.parent.mkdir(parents=True, exist_ok=True)

            if sys.platform == "win32":
                return self._acquire_windows()
            else:
                return self._acquire_posix()

        except Exception as e:
            logger.warning(f"Failed to acquire instance lock: {e}")
            # If locking fails, allow the app to run (better than blocking)
            return True

    def _acquire_windows(self) -> bool:
        """Acquire lock using Windows file locking."""
        import msvcrt

        try:
            # Open in r+/create mode to avoid truncating before we have the lock
            # Create file if it doesn't exist
            if not self._lock_file.exists():
                self._lock_file.touch()
            self._lock_handle = open(self._lock_file, "r+")
            # msvcrt.locking locks from current position; ensure we lock byte 0
            self._lock_handle.seek(0)
            msvcrt.locking(self._lock_handle.fileno(), msvcrt.LK_NBLCK, 1)
            # Lock acquired, now safe to truncate and write our PID
            self._lock_handle.seek(0)
            self._lock_handle.truncate()
            self._lock_handle.write(str(os.getpid()))
            self._lock_handle.flush()
            return True
        except (OSError, IOError):
            if self._lock_handle:
                self._lock_handle.close()
                self._lock_handle = None
            return False

    def _acquire_posix(self) -> bool:
        """Acquire lock using POSIX file locking."""
        import fcntl

        try:
            # Open in r+/create mode to avoid truncating before we have the lock
            if not self._lock_file.exists():
                self._lock_file.touch()
            self._lock_handle = open(self._lock_file, "r+")
            fcntl.flock(self._lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            # Lock acquired, now safe to truncate and write our PID
            self._lock_handle.seek(0)
            self._lock_handle.truncate()
            self._lock_handle.write(str(os.getpid()))
            self._lock_handle.flush()
            return True
        except (OSError, IOError):
            if self._lock_handle:
                self._lock_handle.close()
                self._lock_handle = None
            return False

    def release(self) -> None:
        """Release the instance lock."""
        try:
            if self._lock_handle:
                if sys.platform == "win32":
                    import msvcrt
                    try:
                        msvcrt.locking(self._lock_handle.fileno(), msvcrt.LK_UNLCK, 1)
                    except (OSError, IOError):
                        pass
                else:
                    import fcntl
                    fcntl.flock(self._lock_handle.fileno(), fcntl.LOCK_UN)

                self._lock_handle.close()
                self._lock_handle = None

            if self._lock_file.exists():
                self._lock_file.unlink(missing_ok=True)

        except Exception as e:
            logger.debug(f"Failed to release instance lock: {e}")

    def __enter__(self) -> "SingleInstanceLock":
        if not self.acquire():
            raise RuntimeError("Another instance of ElivroImagine is already running")
        return self

    def __exit__(self, *args: object) -> None:
        self.release()


def check_disk_space(path: Path, required_mb: int = 100) -> tuple[bool, int]:
    """Check if sufficient disk space is available.

    Args:
        path: Path to check disk space for.
        required_mb: Minimum required space in MB.

    Returns:
        Tuple of (has_sufficient_space, available_mb).
    """
    try:
        usage = shutil.disk_usage(str(path))
        available_mb = int(usage.free / (1024 * 1024))
        return available_mb >= required_mb, available_mb
    except Exception as e:
        logger.warning(f"Failed to check disk space: {e}")
        # If we can't check, assume there's enough space
        return True, -1

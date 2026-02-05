"""Tests for utils module."""

from pathlib import Path
from unittest.mock import patch

import pytest

from elivroimagine.utils import SingleInstanceLock, check_disk_space


class TestSingleInstanceLock:
    """Tests for single instance lock."""

    def test_acquire_succeeds_first_time(self, tmp_path: Path) -> None:
        """First acquire should succeed."""
        lock = SingleInstanceLock(tmp_path / "test.lock")
        assert lock.acquire() is True
        lock.release()

    def test_second_acquire_fails(self, tmp_path: Path) -> None:
        """Second acquire on same lock file should fail."""
        lock_file = tmp_path / "test.lock"
        lock1 = SingleInstanceLock(lock_file)
        lock2 = SingleInstanceLock(lock_file)

        assert lock1.acquire() is True
        assert lock2.acquire() is False

        lock1.release()

    def test_release_allows_reacquire(self, tmp_path: Path) -> None:
        """After release, lock can be acquired again."""
        lock_file = tmp_path / "test.lock"
        lock1 = SingleInstanceLock(lock_file)

        assert lock1.acquire() is True
        lock1.release()

        lock2 = SingleInstanceLock(lock_file)
        assert lock2.acquire() is True
        lock2.release()

    def test_context_manager_acquires_and_releases(self, tmp_path: Path) -> None:
        """Context manager acquires on enter and releases on exit."""
        lock_file = tmp_path / "test.lock"

        with SingleInstanceLock(lock_file) as lock:
            # Lock should be acquired (lock file exists)
            assert lock._lock_handle is not None

        # After context exit, should be able to acquire again
        lock2 = SingleInstanceLock(lock_file)
        assert lock2.acquire() is True
        lock2.release()

    def test_context_manager_raises_on_conflict(self, tmp_path: Path) -> None:
        """Context manager raises RuntimeError when lock is held."""
        lock_file = tmp_path / "test.lock"
        lock1 = SingleInstanceLock(lock_file)
        lock1.acquire()

        with pytest.raises(RuntimeError, match="already running"):
            with SingleInstanceLock(lock_file):
                pass

        lock1.release()

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        """Lock file parent directories are created if needed."""
        lock_file = tmp_path / "nested" / "dir" / "test.lock"
        lock = SingleInstanceLock(lock_file)

        assert lock.acquire() is True
        assert lock_file.parent.exists()
        lock.release()

    def test_release_without_acquire_is_safe(self, tmp_path: Path) -> None:
        """Releasing a lock that was never acquired doesn't crash."""
        lock = SingleInstanceLock(tmp_path / "test.lock")
        lock.release()  # Should not raise


class TestCheckDiskSpace:
    """Tests for disk space checking."""

    def test_returns_true_when_enough_space(self, tmp_path: Path) -> None:
        """Returns True when sufficient disk space is available."""
        has_space, available_mb = check_disk_space(tmp_path, required_mb=1)
        assert has_space is True
        assert available_mb > 0

    def test_returns_false_when_not_enough_space(self, tmp_path: Path) -> None:
        """Returns False when required space exceeds available."""
        # Request an absurdly large amount
        has_space, available_mb = check_disk_space(
            tmp_path, required_mb=999_999_999
        )
        assert has_space is False
        assert available_mb >= 0

    def test_returns_available_mb(self, tmp_path: Path) -> None:
        """Returns accurate available MB value."""
        has_space, available_mb = check_disk_space(tmp_path, required_mb=1)
        assert isinstance(available_mb, int)
        assert available_mb > 0

    def test_handles_invalid_path_gracefully(self) -> None:
        """Handles non-existent path gracefully."""
        has_space, available_mb = check_disk_space(
            Path("/nonexistent/path/that/does/not/exist"),
            required_mb=100,
        )
        # Should return True (fail-open) when we can't check
        assert has_space is True
        assert available_mb == -1

    def test_handles_disk_usage_error(self, tmp_path: Path) -> None:
        """Handles shutil.disk_usage failure gracefully."""
        with patch("elivroimagine.utils.shutil.disk_usage", side_effect=OSError):
            has_space, available_mb = check_disk_space(tmp_path, required_mb=100)
            # Should fail-open
            assert has_space is True
            assert available_mb == -1

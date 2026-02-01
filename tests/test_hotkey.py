"""Tests for hotkey listener with debounce functionality."""

import time
from unittest.mock import MagicMock, patch

import pytest


class TestHotkeyDebounce:
    """Test debounce functionality in HotkeyListener."""

    def test_rapid_activations_debounced_in_toggle_mode(
        self, mock_pynput: MagicMock
    ) -> None:
        """Multiple presses within 300ms only fire once."""
        from elivroimagine.hotkey import HotkeyListener

        on_start = MagicMock()
        on_stop = MagicMock()

        listener = HotkeyListener(
            combination="<ctrl>+<alt>+r",
            mode="toggle",
            on_start=on_start,
            on_stop=on_stop,
        )

        # Simulate rapid activations (within debounce window)
        listener._on_hotkey_activate()
        listener._on_hotkey_activate()
        listener._on_hotkey_activate()

        # Only the first activation should fire on_start
        assert on_start.call_count == 1
        assert on_stop.call_count == 0

    def test_activations_after_debounce_window_allowed(
        self, mock_pynput: MagicMock
    ) -> None:
        """Presses after 300ms debounce window work normally."""
        from elivroimagine.hotkey import HotkeyListener

        on_start = MagicMock()
        on_stop = MagicMock()

        listener = HotkeyListener(
            combination="<ctrl>+<alt>+r",
            mode="toggle",
            on_start=on_start,
            on_stop=on_stop,
        )

        # First activation - starts recording
        listener._on_hotkey_activate()
        assert on_start.call_count == 1
        assert on_stop.call_count == 0

        # Wait for debounce window to pass
        time.sleep(0.35)

        # Second activation - stops recording
        listener._on_hotkey_activate()
        assert on_start.call_count == 1
        assert on_stop.call_count == 1

        # Wait for debounce window to pass again
        time.sleep(0.35)

        # Third activation - starts recording again
        listener._on_hotkey_activate()
        assert on_start.call_count == 2
        assert on_stop.call_count == 1

    def test_hold_mode_debounces_start(self, mock_pynput: MagicMock) -> None:
        """Hold mode doesn't double-trigger start on rapid key repeat."""
        from elivroimagine.hotkey import HotkeyListener

        on_start = MagicMock()
        on_stop = MagicMock()

        listener = HotkeyListener(
            combination="<ctrl>+<alt>+r",
            mode="hold",
            on_start=on_start,
            on_stop=on_stop,
        )

        # Simulate rapid activations due to key repeat
        listener._on_hotkey_activate()
        listener._on_hotkey_activate()
        listener._on_hotkey_activate()

        # Only one start should be triggered
        assert on_start.call_count == 1
        assert on_stop.call_count == 0

    def test_hold_mode_key_release_debounced(self, mock_pynput: MagicMock) -> None:
        """Hold mode key release is debounced."""
        from pynput import keyboard

        from elivroimagine.hotkey import HotkeyListener

        on_start = MagicMock()
        on_stop = MagicMock()

        listener = HotkeyListener(
            combination="<ctrl>+<alt>+r",
            mode="hold",
            on_start=on_start,
            on_stop=on_stop,
        )

        # Start recording
        listener._on_hotkey_activate()
        assert on_start.call_count == 1

        # Immediate key release should be debounced
        mock_key = MagicMock()
        mock_key.name = "ctrl_l"
        listener._on_key_release(mock_key)

        # on_stop should be debounced because it's within 300ms of on_start
        assert on_stop.call_count == 0

    def test_hold_mode_key_release_after_debounce(
        self, mock_pynput: MagicMock
    ) -> None:
        """Hold mode key release works after debounce window."""
        from pynput import keyboard

        from elivroimagine.hotkey import HotkeyListener

        on_start = MagicMock()
        on_stop = MagicMock()

        listener = HotkeyListener(
            combination="<ctrl>+<alt>+r",
            mode="hold",
            on_start=on_start,
            on_stop=on_stop,
        )

        # Start recording
        listener._on_hotkey_activate()
        assert on_start.call_count == 1

        # Wait for debounce
        time.sleep(0.35)

        # Now key release should work
        mock_key = MagicMock()
        mock_key.name = "ctrl_l"
        listener._on_key_release(mock_key)

        assert on_stop.call_count == 1


class TestHotkeyToggleMode:
    """Test toggle mode behavior."""

    def test_toggle_mode_alternates_start_stop(self, mock_pynput: MagicMock) -> None:
        """Toggle mode alternates between start and stop."""
        from elivroimagine.hotkey import HotkeyListener

        on_start = MagicMock()
        on_stop = MagicMock()

        listener = HotkeyListener(
            combination="<ctrl>+<alt>+r",
            mode="toggle",
            on_start=on_start,
            on_stop=on_stop,
        )

        # First press - start
        listener._on_hotkey_activate()
        assert listener.is_active is True
        assert on_start.call_count == 1

        # Wait for debounce
        time.sleep(0.35)

        # Second press - stop
        listener._on_hotkey_activate()
        assert listener.is_active is False
        assert on_stop.call_count == 1


class TestHotkeyHoldMode:
    """Test hold mode behavior."""

    def test_hold_mode_start_on_press(self, mock_pynput: MagicMock) -> None:
        """Hold mode starts recording on key press."""
        from elivroimagine.hotkey import HotkeyListener

        on_start = MagicMock()
        on_stop = MagicMock()

        listener = HotkeyListener(
            combination="<ctrl>+<alt>+r",
            mode="hold",
            on_start=on_start,
            on_stop=on_stop,
        )

        listener._on_hotkey_activate()

        assert listener.is_active is True
        assert on_start.call_count == 1
        assert on_stop.call_count == 0

    def test_hold_mode_ignores_non_combo_key_release(
        self, mock_pynput: MagicMock
    ) -> None:
        """Hold mode ignores release of keys not in combo."""
        from elivroimagine.hotkey import HotkeyListener

        on_start = MagicMock()
        on_stop = MagicMock()

        listener = HotkeyListener(
            combination="<ctrl>+<alt>+r",
            mode="hold",
            on_start=on_start,
            on_stop=on_stop,
        )

        # Start recording
        listener._on_hotkey_activate()

        # Wait for debounce
        time.sleep(0.35)

        # Release unrelated key
        mock_key = MagicMock()
        mock_key.name = "space"
        listener._on_key_release(mock_key)

        # Should still be active
        assert listener.is_active is True
        assert on_stop.call_count == 0


class TestHotkeyLifecycle:
    """Test hotkey listener start/stop."""

    def test_start_creates_listeners(self, mock_pynput: MagicMock) -> None:
        """Starting listener creates pynput listeners."""
        from elivroimagine.hotkey import HotkeyListener

        listener = HotkeyListener(
            combination="<ctrl>+<alt>+r",
            mode="toggle",
            on_start=MagicMock(),
            on_stop=MagicMock(),
        )

        listener.start()

        mock_pynput.GlobalHotKeys.assert_called_once()
        assert listener._listener is not None

    def test_stop_cleans_up_listeners(self, mock_pynput: MagicMock) -> None:
        """Stopping listener cleans up resources."""
        from elivroimagine.hotkey import HotkeyListener

        listener = HotkeyListener(
            combination="<ctrl>+<alt>+r",
            mode="toggle",
            on_start=MagicMock(),
            on_stop=MagicMock(),
        )

        listener.start()
        listener.stop()

        assert listener._listener is None
        assert listener._is_active is False

    def test_update_combination_restarts_listener(
        self, mock_pynput: MagicMock
    ) -> None:
        """Updating combination restarts the listener."""
        from elivroimagine.hotkey import HotkeyListener

        listener = HotkeyListener(
            combination="<ctrl>+<alt>+r",
            mode="toggle",
            on_start=MagicMock(),
            on_stop=MagicMock(),
        )

        listener.start()
        listener.update_combination("<ctrl>+<shift>+r")

        assert listener.combination == "<ctrl>+<shift>+r"
        # Should have created a new listener
        assert mock_pynput.GlobalHotKeys.call_count == 2

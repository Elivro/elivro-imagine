"""Tests for hotkey listener with keyboard library and scan code support."""

import time
from unittest.mock import MagicMock, patch

import pytest


class TestHotkeyDebounce:
    """Test debounce functionality in HotkeyListener."""

    def test_toggle_mode_alternates_on_each_activate(
        self, mock_pynput: MagicMock
    ) -> None:
        """Each _on_hotkey_activate call toggles state."""
        from elivroimagine.hotkey import HotkeyListener

        on_start = MagicMock()
        on_stop = MagicMock()

        listener = HotkeyListener(
            combination="<ctrl>+<alt>+r",
            mode="toggle",
            on_start=on_start,
            on_stop=on_stop,
        )

        # First activation - start
        listener._on_hotkey_activate()
        assert on_start.call_count == 1
        assert on_stop.call_count == 0

        # Second activation - stop
        listener._on_hotkey_activate()
        assert on_start.call_count == 1
        assert on_stop.call_count == 1

        # Third activation - start again
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

    def test_hold_mode_release_stops_immediately(
        self, mock_pynput: MagicMock
    ) -> None:
        """Hold mode key release stops recording immediately - no debounce."""
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

        # Immediate key release should stop (no debounce on release)
        listener._on_hold_release()

        assert on_stop.call_count == 1
        assert listener.is_active is False


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

    def test_hold_mode_release_stops(
        self, mock_pynput: MagicMock
    ) -> None:
        """Hold mode stops on release."""
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

        # Release should stop
        listener._on_hold_release()

        assert listener.is_active is False
        assert on_stop.call_count == 1

    def test_hold_mode_mouse_release_stops_immediately(
        self, mock_pynput: MagicMock
    ) -> None:
        """Mouse button release in hold mode stops immediately."""
        from elivroimagine.hotkey import HotkeyListener

        on_start = MagicMock()
        on_stop = MagicMock()

        listener = HotkeyListener(
            combination="<mouse_middle>",
            mode="hold",
            on_start=on_start,
            on_stop=on_stop,
        )

        # Start via _on_hotkey_activate (simulates mouse press)
        listener._on_hotkey_activate()
        assert on_start.call_count == 1
        assert listener.is_active is True

        # Immediate release - should stop without delay
        listener._on_hold_release()
        assert on_stop.call_count == 1
        assert listener.is_active is False


class TestHotkeyLifecycle:
    """Test hotkey listener start/stop."""

    def test_start_registers_hotkey(self, mock_pynput: MagicMock) -> None:
        """Starting listener registers hotkey with keyboard library."""
        from elivroimagine.hotkey import HotkeyListener

        listener = HotkeyListener(
            combination="<ctrl>+<alt>+r",
            mode="toggle",
            on_start=MagicMock(),
            on_stop=MagicMock(),
        )

        listener.start()

        mock_pynput.add_hotkey.assert_called_once()
        assert listener._hotkey_id is not None

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

        assert listener._hotkey_id is None
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
        # Should have registered hotkey twice (once on start, once on update)
        assert mock_pynput.add_hotkey.call_count == 2


class TestScanCodeSupport:
    """Test scan code based hotkey detection."""

    def test_listener_with_scan_code(self, mock_pynput: MagicMock) -> None:
        """Listener can be initialized with a scan code."""
        from elivroimagine.hotkey import HotkeyListener

        listener = HotkeyListener(
            combination="§",
            mode="hold",
            on_start=MagicMock(),
            on_stop=MagicMock(),
            scan_code=41,  # Swedish keyboard § key
        )

        assert listener.scan_code == 41
        assert listener.combination == "§"

    def test_start_with_scan_code_registers_key_hook(
        self, mock_pynput: MagicMock
    ) -> None:
        """Starting listener with scan code registers key hooks."""
        from elivroimagine.hotkey import HotkeyListener

        listener = HotkeyListener(
            combination="§",
            mode="hold",
            on_start=MagicMock(),
            on_stop=MagicMock(),
            scan_code=41,
        )

        listener.start()

        # Should use on_press_key for scan code instead of add_hotkey
        mock_pynput.on_press_key.assert_called()
        # Should not use add_hotkey when scan_code is provided
        mock_pynput.add_hotkey.assert_not_called()

    def test_scan_code_with_modifiers(self, mock_pynput: MagicMock) -> None:
        """Scan code with modifiers registers key hook and checks modifiers."""
        from elivroimagine.hotkey import HotkeyListener

        listener = HotkeyListener(
            combination="<ctrl>+§",
            mode="hold",
            on_start=MagicMock(),
            on_stop=MagicMock(),
            scan_code=41,
        )

        listener.start()

        # Should register press hook for scan code
        mock_pynput.on_press_key.assert_called()

    def test_update_combination_with_scan_code(
        self, mock_pynput: MagicMock
    ) -> None:
        """Updating combination also updates scan code."""
        from elivroimagine.hotkey import HotkeyListener

        listener = HotkeyListener(
            combination="<ctrl>+<alt>+r",
            mode="toggle",
            on_start=MagicMock(),
            on_stop=MagicMock(),
        )

        listener.start()
        listener.update_combination("§", scan_code=41)

        assert listener.combination == "§"
        assert listener.scan_code == 41


class TestCombinationNormalization:
    """Test combination string normalization."""

    def test_normalize_removes_angle_brackets(
        self, mock_pynput: MagicMock
    ) -> None:
        """Normalization removes angle brackets from modifiers."""
        from elivroimagine.hotkey import HotkeyListener

        listener = HotkeyListener(
            combination="<ctrl>+<alt>+r",
            mode="toggle",
            on_start=MagicMock(),
            on_stop=MagicMock(),
        )

        normalized = listener._normalize_combination()
        assert normalized == "ctrl+alt+r"

    def test_normalize_function_keys(self, mock_pynput: MagicMock) -> None:
        """Normalization handles function keys."""
        from elivroimagine.hotkey import HotkeyListener

        listener = HotkeyListener(
            combination="<ctrl>+<f12>",
            mode="toggle",
            on_start=MagicMock(),
            on_stop=MagicMock(),
        )

        normalized = listener._normalize_combination()
        assert normalized == "ctrl+f12"


class TestMouseHotkey:
    """Test mouse button hotkeys (still use pynput for mouse)."""

    def test_is_mouse_hotkey_detection(self, mock_pynput: MagicMock) -> None:
        """Correctly detects mouse button hotkeys."""
        from elivroimagine.hotkey import HotkeyListener

        # Mouse middle button
        listener = HotkeyListener(
            combination="<shift>+<mouse_middle>",
            mode="hold",
            on_start=MagicMock(),
            on_stop=MagicMock(),
        )
        assert listener._is_mouse_hotkey() is True

        # Keyboard only
        listener2 = HotkeyListener(
            combination="<ctrl>+<alt>+r",
            mode="hold",
            on_start=MagicMock(),
            on_stop=MagicMock(),
        )
        assert listener2._is_mouse_hotkey() is False

    def test_get_keyboard_modifiers(self, mock_pynput: MagicMock) -> None:
        """Extracts keyboard modifiers from combination."""
        from elivroimagine.hotkey import HotkeyListener

        listener = HotkeyListener(
            combination="<ctrl>+<shift>+<mouse_middle>",
            mode="hold",
            on_start=MagicMock(),
            on_stop=MagicMock(),
        )

        modifiers = listener._get_keyboard_modifiers()
        assert "ctrl" in modifiers
        assert "shift" in modifiers
        assert len(modifiers) == 2

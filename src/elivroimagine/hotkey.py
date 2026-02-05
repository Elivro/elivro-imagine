"""Global hotkey listener using keyboard library for scan code support."""

import logging
import threading
import time
from typing import Callable, Literal

import keyboard
from pynput import mouse

logger = logging.getLogger(__name__)


class HotkeyListener:
    """Listens for global hotkeys using the keyboard library.

    Supports both key names and scan codes for layout-independent hotkeys.
    When scan_code is provided, it takes precedence over combination parsing.
    """

    def __init__(
        self,
        combination: str,
        mode: Literal["hold", "toggle"],
        on_start: Callable[[], None],
        on_stop: Callable[[], None],
        scan_code: int | None = None,
    ) -> None:
        """Initialize hotkey listener.

        Args:
            combination: Hotkey combination (e.g., "<ctrl>+<alt>+r").
            mode: "hold" (release to stop) or "toggle" (press again to stop).
            on_start: Callback when recording should start.
            on_stop: Callback when recording should stop.
            scan_code: Optional scan code for the main key (layout-independent).
        """
        self.combination = combination
        self.mode = mode
        self.on_start = on_start
        self.on_stop = on_stop
        self.scan_code = scan_code

        self._hotkey_id: int | None = None
        self._mouse_listener: mouse.Listener | None = None
        self._is_active = False
        self._hotkey_pressed = False
        self._lock = threading.Lock()
        self._last_start_time: float = 0.0
        self._start_debounce: float = 0.15  # 150ms - prevents double-start
        self._mouse_button: mouse.Button | None = None
        self._registered_hooks: list[Callable[..., None]] = []

    def _is_mouse_hotkey(self) -> bool:
        """Check if the combination uses a mouse button."""
        combo_lower = self.combination.lower()
        return "<mouse" in combo_lower or "<mouse_middle>" in combo_lower

    def _get_mouse_button(self) -> mouse.Button | None:
        """Parse mouse button from combination."""
        combo_lower = self.combination.lower()
        if "<mouse_middle>" in combo_lower:
            return mouse.Button.middle
        elif "<mouse4>" in combo_lower:
            return mouse.Button.x1
        elif "<mouse5>" in combo_lower:
            return mouse.Button.x2
        return None

    def _get_keyboard_modifiers(self) -> list[str]:
        """Get modifier key names for the keyboard library."""
        combo_lower = self.combination.lower()
        modifiers = []
        if "<ctrl>" in combo_lower:
            modifiers.append("ctrl")
        if "<alt>" in combo_lower:
            modifiers.append("alt")
        if "<shift>" in combo_lower:
            modifiers.append("shift")
        return modifiers

    def _normalize_combination(self) -> str:
        """Convert pynput-style combination to keyboard library format.

        Converts: "<ctrl>+<alt>+r" -> "ctrl+alt+r"
        """
        combo = self.combination.lower()
        # Remove angle brackets from modifiers
        combo = combo.replace("<ctrl>", "ctrl")
        combo = combo.replace("<alt>", "alt")
        combo = combo.replace("<shift>", "shift")
        # Remove angle brackets from function keys like <f1>
        import re
        combo = re.sub(r"<(f\d+)>", r"\1", combo)
        # Remove any remaining angle brackets for single keys
        combo = re.sub(r"<([^>]+)>", r"\1", combo)
        return combo

    def start(self) -> None:
        """Start listening for hotkeys."""
        if self._hotkey_id is not None or self._mouse_listener is not None:
            return

        logger.info(
            f"Starting hotkey listener: {self.combination} "
            f"(mode: {self.mode}, scan_code: {self.scan_code})"
        )

        if self._is_mouse_hotkey():
            # Mouse button hotkey - use pynput for mouse, keyboard for modifiers
            self._mouse_button = self._get_mouse_button()

            self._mouse_listener = mouse.Listener(
                on_click=self._on_mouse_click,
            )
            self._mouse_listener.start()
        else:
            # Keyboard-only hotkey
            if self.scan_code is not None:
                # Use scan code for the main key
                modifiers = self._get_keyboard_modifiers()
                if modifiers:
                    # Register modifier check on scan code press
                    hook = keyboard.on_press_key(
                        self.scan_code,
                        lambda e: self._on_scancode_press(e, modifiers),
                        suppress=True,
                    )
                    self._registered_hooks.append(hook)
                else:
                    # Just the scan code, no modifiers
                    hook = keyboard.on_press_key(
                        self.scan_code,
                        self._on_key_press_event,
                        suppress=True,
                    )
                    self._registered_hooks.append(hook)

                # Register release handler for hold mode
                if self.mode == "hold":
                    release_hook = keyboard.on_release_key(
                        self.scan_code,
                        self._on_key_release_event,
                        suppress=True,
                    )
                    self._registered_hooks.append(release_hook)
            else:
                # Use combination string
                combo = self._normalize_combination()
                try:
                    self._hotkey_id = keyboard.add_hotkey(
                        combo,
                        self._on_hotkey_activate,
                        suppress=True,
                        trigger_on_release=False,
                    )
                except ValueError as e:
                    logger.error(f"Invalid hotkey combination '{combo}': {e}")
                    return

                # For hold mode, track key releases
                if self.mode == "hold":
                    # Extract the main key (last part of combination)
                    parts = combo.split("+")
                    main_key = parts[-1] if parts else combo
                    release_hook = keyboard.on_release_key(
                        main_key,
                        self._on_key_release_event,
                        suppress=True,
                    )
                    self._registered_hooks.append(release_hook)

    def _on_scancode_press(
        self, event: keyboard.KeyboardEvent, required_modifiers: list[str]
    ) -> None:
        """Handle scan code press with modifier check."""
        # Check if all required modifiers are currently pressed
        for mod in required_modifiers:
            if not keyboard.is_pressed(mod):
                return
        self._on_hotkey_activate()

    def _on_key_press_event(self, event: keyboard.KeyboardEvent) -> None:
        """Handle key press event (for scan code without modifiers)."""
        self._on_hotkey_activate()

    def _on_key_release_event(self, event: keyboard.KeyboardEvent) -> None:
        """Handle key release for hold mode."""
        if self.mode != "hold":
            return
        self._on_hold_release()

    def stop(self) -> None:
        """Stop listening for hotkeys."""
        if self._hotkey_id is not None:
            try:
                keyboard.remove_hotkey(self._hotkey_id)
            except (KeyError, ValueError):
                pass  # Already removed
            self._hotkey_id = None

        # Remove all registered hooks
        for hook in self._registered_hooks:
            try:
                keyboard.unhook(hook)
            except (KeyError, ValueError):
                pass
        self._registered_hooks.clear()

        if self._mouse_listener:
            self._mouse_listener.stop()
            self._mouse_listener = None

        self._is_active = False
        self._hotkey_pressed = False

    def _on_mouse_click(
        self, x: int, y: int, button: mouse.Button, pressed: bool
    ) -> None:
        """Handle mouse button clicks for mouse button hotkeys."""
        if button != self._mouse_button:
            return

        # Check if required modifiers are pressed using keyboard library
        modifiers = self._get_keyboard_modifiers()
        for mod in modifiers:
            if not keyboard.is_pressed(mod):
                return

        if pressed:
            self._on_hotkey_activate()
        else:
            if self.mode == "hold" and self._is_active:
                self._on_hold_release()

    def _on_hold_release(self) -> None:
        """Handle release in hold mode.

        No debounce on release - the app's duration check (< 0.5s)
        handles accidental taps.
        """
        with self._lock:
            if self._is_active:
                self._is_active = False
                self._hotkey_pressed = False
                logger.debug("Hold: stopping recording (released)")
                self.on_stop()

    def _on_hotkey_activate(self) -> None:
        """Handle hotkey activation."""
        current_time = time.time()

        with self._lock:
            if self.mode == "toggle":
                if self._is_active:
                    self._is_active = False
                    logger.debug("Toggle: stopping recording")
                    self.on_stop()
                else:
                    self._is_active = True
                    logger.debug("Toggle: starting recording")
                    self.on_start()
            else:  # hold mode
                # Debounce start only - prevents double-start from rapid press events
                if current_time - self._last_start_time < self._start_debounce:
                    logger.debug("Hold start debounced")
                    return

                if not self._is_active:
                    self._last_start_time = current_time
                    self._is_active = True
                    self._hotkey_pressed = True
                    logger.debug("Hold: starting recording")
                    self.on_start()

    def update_combination(
        self, combination: str, scan_code: int | None = None
    ) -> None:
        """Update the hotkey combination."""
        was_running = self._hotkey_id is not None or self._mouse_listener is not None
        if was_running:
            self.stop()
        self.combination = combination
        self.scan_code = scan_code
        if was_running:
            self.start()

    def update_mode(self, mode: Literal["hold", "toggle"]) -> None:
        """Update the recording mode."""
        was_running = self._hotkey_id is not None or self._mouse_listener is not None
        if was_running:
            self.stop()
        self.mode = mode
        if was_running:
            self.start()

    @property
    def is_active(self) -> bool:
        """Check if recording is currently active."""
        return self._is_active

    # Backward compatibility methods for tests
    def _on_key_release(self, key: object) -> None:
        """Legacy method for test compatibility - delegates to _on_hold_release."""
        if self.mode == "hold" and self._hotkey_pressed:
            self._on_hold_release()

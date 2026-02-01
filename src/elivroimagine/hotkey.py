"""Global hotkey listener using pynput."""

import logging
import threading
import time
from typing import Callable, Literal

from pynput import keyboard

logger = logging.getLogger(__name__)


class HotkeyListener:
    """Listens for global hotkeys."""

    def __init__(
        self,
        combination: str,
        mode: Literal["hold", "toggle"],
        on_start: Callable[[], None],
        on_stop: Callable[[], None],
    ) -> None:
        """Initialize hotkey listener.

        Args:
            combination: Hotkey combination (e.g., "<ctrl>+<alt>+r").
            mode: "hold" (release to stop) or "toggle" (press again to stop).
            on_start: Callback when recording should start.
            on_stop: Callback when recording should stop.
        """
        self.combination = combination
        self.mode = mode
        self.on_start = on_start
        self.on_stop = on_stop

        self._listener: keyboard.GlobalHotKeys | None = None
        self._key_listener: keyboard.Listener | None = None
        self._is_active = False
        self._hotkey_pressed = False
        self._lock = threading.Lock()
        self._last_activation_time: float = 0.0
        self._debounce_interval: float = 0.3  # 300ms debounce

    def _parse_combination(self) -> set[keyboard.Key | keyboard.KeyCode]:
        """Parse combination string to key set."""
        keys: set[keyboard.Key | keyboard.KeyCode] = set()
        parts = self.combination.lower().split("+")

        for part in parts:
            part = part.strip()
            if part == "<ctrl>":
                keys.add(keyboard.Key.ctrl_l)
            elif part == "<alt>":
                keys.add(keyboard.Key.alt_l)
            elif part == "<shift>":
                keys.add(keyboard.Key.shift_l)
            elif part.startswith("<") and part.endswith(">"):
                key_name = part[1:-1]
                try:
                    keys.add(getattr(keyboard.Key, key_name))
                except AttributeError:
                    keys.add(keyboard.KeyCode.from_char(key_name))
            else:
                keys.add(keyboard.KeyCode.from_char(part))

        return keys

    def start(self) -> None:
        """Start listening for hotkeys."""
        if self._listener is not None:
            return

        logger.info(f"Starting hotkey listener: {self.combination} (mode: {self.mode})")

        # Use GlobalHotKeys for simpler handling
        hotkeys = {self.combination: self._on_hotkey_activate}
        self._listener = keyboard.GlobalHotKeys(hotkeys)
        self._listener.start()

        # Also listen for key releases in hold mode
        if self.mode == "hold":
            self._key_listener = keyboard.Listener(on_release=self._on_key_release)
            self._key_listener.start()

    def stop(self) -> None:
        """Stop listening for hotkeys."""
        if self._listener:
            self._listener.stop()
            self._listener = None

        if self._key_listener:
            self._key_listener.stop()
            self._key_listener = None

        self._is_active = False
        self._hotkey_pressed = False

    def _on_hotkey_activate(self) -> None:
        """Handle hotkey activation."""
        current_time = time.time()

        with self._lock:
            # Debounce: skip if called within debounce window
            if current_time - self._last_activation_time < self._debounce_interval:
                logger.debug("Hotkey activation debounced")
                return

            self._last_activation_time = current_time

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
                if not self._is_active:
                    self._is_active = True
                    self._hotkey_pressed = True
                    logger.debug("Hold: starting recording")
                    self.on_start()

    def _on_key_release(self, key: keyboard.Key | keyboard.KeyCode) -> None:
        """Handle key release for hold mode."""
        if self.mode != "hold" or not self._hotkey_pressed:
            return

        # Check if any modifier key in the combination was released
        combo_lower = self.combination.lower()
        released_key_name = ""

        if hasattr(key, "name"):
            released_key_name = key.name
        elif hasattr(key, "char"):
            released_key_name = key.char or ""

        # Check if released key is part of the hotkey
        is_part_of_combo = False
        if "ctrl" in combo_lower and "ctrl" in released_key_name:
            is_part_of_combo = True
        elif "alt" in combo_lower and "alt" in released_key_name:
            is_part_of_combo = True
        elif "shift" in combo_lower and "shift" in released_key_name:
            is_part_of_combo = True
        elif released_key_name and f"+{released_key_name}" in combo_lower:
            is_part_of_combo = True
        elif released_key_name and combo_lower.endswith(released_key_name):
            is_part_of_combo = True

        if is_part_of_combo:
            current_time = time.time()

            with self._lock:
                # Debounce: skip if called within debounce window
                if current_time - self._last_activation_time < self._debounce_interval:
                    logger.debug("Key release debounced")
                    return

                if self._is_active:
                    self._last_activation_time = current_time
                    self._is_active = False
                    self._hotkey_pressed = False
                    logger.debug("Hold: stopping recording (key released)")
                    self.on_stop()

    def update_combination(self, combination: str) -> None:
        """Update the hotkey combination."""
        was_running = self._listener is not None
        if was_running:
            self.stop()
        self.combination = combination
        if was_running:
            self.start()

    def update_mode(self, mode: Literal["hold", "toggle"]) -> None:
        """Update the recording mode."""
        was_running = self._listener is not None
        if was_running:
            self.stop()
        self.mode = mode
        if was_running:
            self.start()

    @property
    def is_active(self) -> bool:
        """Check if recording is currently active."""
        return self._is_active

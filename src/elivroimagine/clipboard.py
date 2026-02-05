"""Clipboard paste functionality via Win32 API."""

import logging
import sys
import time

logger = logging.getLogger(__name__)


class Paster:
    """Pastes text into the currently focused field via clipboard + Ctrl+V."""

    def __init__(self, restore_clipboard: bool = False) -> None:
        """Initialize paster.

        Args:
            restore_clipboard: Whether to restore clipboard contents after pasting.
                               Default is False - the transcription stays in clipboard.
        """
        self.restore_clipboard = restore_clipboard

        if sys.platform != "win32":
            logger.warning("Paster only works on Windows")

    def paste_text(self, text: str) -> bool:
        """Paste text into the currently focused field.

        Sets text to clipboard → simulates Ctrl+V.

        Args:
            text: Text to paste.

        Returns:
            True if paste succeeded, False otherwise.
        """
        if sys.platform != "win32":
            logger.error("Paste is only supported on Windows")
            return False

        if not text:
            logger.warning("Empty text provided to paste")
            return False

        saved_text: str | None = None

        try:
            # Save current clipboard if restore is enabled
            if self.restore_clipboard:
                saved_text = self._get_clipboard()
                logger.debug(f"Saved clipboard: {len(saved_text) if saved_text else 0} chars")

            # Set our text to clipboard with retries
            if not self._set_clipboard_with_retry(text):
                logger.error("Failed to set clipboard text after retries")
                return False

            # Verify clipboard was set correctly
            verify = self._get_clipboard()
            if verify != text:
                logger.error(f"Clipboard verification failed: expected {len(text)} chars, got {len(verify) if verify else 0}")
                return False

            logger.info(f"Clipboard set successfully: {len(text)} chars")

            # Small delay to ensure clipboard is ready
            time.sleep(0.05)

            # Simulate Ctrl+V using SendInput
            self._simulate_ctrl_v()

            # Delay to let the paste complete before any restore
            time.sleep(0.2)

            return True

        except Exception as e:
            logger.error(f"Paste failed: {e}", exc_info=True)
            return False

        finally:
            # Restore clipboard after a longer delay (if enabled)
            if self.restore_clipboard and saved_text is not None:
                time.sleep(0.5)  # Wait for paste to fully complete
                self._set_clipboard(saved_text)

    def _get_clipboard(self) -> str | None:
        """Get current clipboard text.

        Returns:
            Clipboard text, or None if clipboard doesn't contain text.
        """
        try:
            import ctypes
            from ctypes import wintypes

            CF_UNICODETEXT = 13
            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32

            user32.OpenClipboard.argtypes = [wintypes.HWND]
            user32.OpenClipboard.restype = wintypes.BOOL
            user32.CloseClipboard.argtypes = []
            user32.CloseClipboard.restype = wintypes.BOOL
            user32.GetClipboardData.argtypes = [wintypes.UINT]
            user32.GetClipboardData.restype = wintypes.HANDLE

            if not user32.OpenClipboard(None):
                return None

            try:
                if not user32.IsClipboardFormatAvailable(CF_UNICODETEXT):
                    return None

                handle = user32.GetClipboardData(CF_UNICODETEXT)
                if not handle:
                    return None

                ptr = kernel32.GlobalLock(handle)
                if not ptr:
                    return None

                try:
                    return ctypes.wstring_at(ptr)
                finally:
                    kernel32.GlobalUnlock(handle)
            finally:
                user32.CloseClipboard()

        except Exception as e:
            logger.debug(f"Failed to get clipboard: {e}")
            return None

    def _set_clipboard(self, text: str) -> bool:
        """Set clipboard text using Win32 API.

        Args:
            text: Text to set.

        Returns:
            True if successful.
        """
        try:
            import ctypes
            from ctypes import wintypes, c_size_t, c_void_p, c_wchar_p

            CF_UNICODETEXT = 13
            GMEM_MOVEABLE = 0x0002

            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32

            # Properly declare all function signatures
            kernel32.GlobalAlloc.argtypes = [wintypes.UINT, c_size_t]
            kernel32.GlobalAlloc.restype = wintypes.HGLOBAL

            kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
            kernel32.GlobalLock.restype = c_void_p

            kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
            kernel32.GlobalUnlock.restype = wintypes.BOOL

            kernel32.GlobalFree.argtypes = [wintypes.HGLOBAL]
            kernel32.GlobalFree.restype = wintypes.HGLOBAL

            user32.OpenClipboard.argtypes = [wintypes.HWND]
            user32.OpenClipboard.restype = wintypes.BOOL
            user32.CloseClipboard.argtypes = []
            user32.CloseClipboard.restype = wintypes.BOOL
            user32.EmptyClipboard.argtypes = []
            user32.EmptyClipboard.restype = wintypes.BOOL
            user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
            user32.SetClipboardData.restype = wintypes.HANDLE

            # Encode text as wide string (UTF-16 LE with null terminator)
            text_with_null = text + "\0"
            buf_size = len(text_with_null) * 2  # 2 bytes per UTF-16 char

            h_mem = kernel32.GlobalAlloc(GMEM_MOVEABLE, buf_size)
            if not h_mem:
                logger.error(f"GlobalAlloc failed for {buf_size} bytes")
                return False

            ptr = kernel32.GlobalLock(h_mem)
            if not ptr:
                err = ctypes.get_last_error()
                kernel32.GlobalFree(h_mem)
                logger.error(f"GlobalLock failed, error code: {err}")
                return False

            try:
                # Copy the text using ctypes
                ctypes.memmove(ptr, text_with_null.encode("utf-16-le"), buf_size)
            finally:
                kernel32.GlobalUnlock(h_mem)

            if not user32.OpenClipboard(None):
                err = ctypes.get_last_error()
                kernel32.GlobalFree(h_mem)
                logger.error(f"OpenClipboard failed, error code: {err}")
                return False

            try:
                user32.EmptyClipboard()
                result = user32.SetClipboardData(CF_UNICODETEXT, h_mem)
                if not result:
                    err = ctypes.get_last_error()
                    logger.error(f"SetClipboardData failed, error code: {err}")
                    return False
                # Don't free h_mem - clipboard owns it now
                return True
            finally:
                user32.CloseClipboard()

        except Exception as e:
            logger.error(f"Failed to set clipboard: {e}", exc_info=True)
            return False

    def _set_clipboard_with_retry(self, text: str, max_retries: int = 3) -> bool:
        """Set clipboard with retries in case another app has it locked.

        Args:
            text: Text to set.
            max_retries: Maximum number of attempts.

        Returns:
            True if successful.
        """
        for attempt in range(max_retries):
            if self._set_clipboard(text):
                return True
            logger.warning(f"Clipboard set attempt {attempt + 1} failed, retrying...")
            time.sleep(0.1 * (attempt + 1))  # Increasing backoff
        return False

    def _simulate_ctrl_v(self) -> None:
        """Simulate Ctrl+V keystroke using SendInput API."""
        import ctypes
        from ctypes import wintypes, sizeof, POINTER, c_ulong, Structure, Union

        # Virtual key codes
        VK_CONTROL = 0x11
        VK_V = 0x56

        # Input types and flags
        INPUT_KEYBOARD = 1
        KEYEVENTF_KEYUP = 0x0002

        # Proper structure definitions for SendInput
        ULONG_PTR = ctypes.POINTER(ctypes.c_ulong)

        class KEYBDINPUT(Structure):
            _fields_ = [
                ("wVk", wintypes.WORD),
                ("wScan", wintypes.WORD),
                ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD),
                ("dwExtraInfo", ULONG_PTR),
            ]

        class MOUSEINPUT(Structure):
            _fields_ = [
                ("dx", wintypes.LONG),
                ("dy", wintypes.LONG),
                ("mouseData", wintypes.DWORD),
                ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD),
                ("dwExtraInfo", ULONG_PTR),
            ]

        class HARDWAREINPUT(Structure):
            _fields_ = [
                ("uMsg", wintypes.DWORD),
                ("wParamL", wintypes.WORD),
                ("wParamH", wintypes.WORD),
            ]

        class INPUT_UNION(Union):
            _fields_ = [
                ("mi", MOUSEINPUT),
                ("ki", KEYBDINPUT),
                ("hi", HARDWAREINPUT),
            ]

        class INPUT(Structure):
            _fields_ = [
                ("type", wintypes.DWORD),
                ("union", INPUT_UNION),
            ]

        user32 = ctypes.windll.user32
        user32.SendInput.argtypes = [wintypes.UINT, POINTER(INPUT), ctypes.c_int]
        user32.SendInput.restype = wintypes.UINT

        # Create input events: Ctrl down, V down, V up, Ctrl up
        inputs = (INPUT * 4)()

        # Ctrl down
        inputs[0].type = INPUT_KEYBOARD
        inputs[0].union.ki.wVk = VK_CONTROL
        inputs[0].union.ki.dwFlags = 0

        # V down
        inputs[1].type = INPUT_KEYBOARD
        inputs[1].union.ki.wVk = VK_V
        inputs[1].union.ki.dwFlags = 0

        # V up
        inputs[2].type = INPUT_KEYBOARD
        inputs[2].union.ki.wVk = VK_V
        inputs[2].union.ki.dwFlags = KEYEVENTF_KEYUP

        # Ctrl up
        inputs[3].type = INPUT_KEYBOARD
        inputs[3].union.ki.wVk = VK_CONTROL
        inputs[3].union.ki.dwFlags = KEYEVENTF_KEYUP

        # Send all inputs at once
        sent = user32.SendInput(4, inputs, sizeof(INPUT))
        if sent != 4:
            err = ctypes.get_last_error()
            logger.warning(f"SendInput only sent {sent}/4 events, error: {err}")
            # Fallback to pynput
            logger.info("Falling back to pynput for Ctrl+V")
            self._pynput_paste()
        else:
            logger.debug("SendInput Ctrl+V sent successfully")

    def _pynput_paste(self) -> None:
        """Fallback: Simulate Ctrl+V using pynput."""
        try:
            from pynput.keyboard import Controller, Key

            kb = Controller()
            kb.press(Key.ctrl)
            kb.press('v')
            kb.release('v')
            kb.release(Key.ctrl)
            logger.debug("pynput Ctrl+V sent")
        except Exception as e:
            logger.error(f"pynput paste failed: {e}")

"""Tests for clipboard module."""

import sys
from unittest.mock import MagicMock, patch

import pytest


class TestPasterInit:
    """Tests for Paster initialization."""

    def test_default_restore_clipboard_is_false(self) -> None:
        """Default restore_clipboard should be False to keep transcription in clipboard."""
        from elivroimagine.clipboard import Paster

        paster = Paster()
        assert paster.restore_clipboard is False

    def test_enable_restore_clipboard(self) -> None:
        """Can enable restore_clipboard."""
        from elivroimagine.clipboard import Paster

        paster = Paster(restore_clipboard=True)
        assert paster.restore_clipboard is True


class TestPasterPasteText:
    """Tests for Paster.paste_text method."""

    def test_paste_empty_text_returns_false(self) -> None:
        """Pasting empty text returns False."""
        from elivroimagine.clipboard import Paster

        paster = Paster()
        result = paster.paste_text("")
        assert result is False

    @patch.object(sys, "platform", "linux")
    def test_paste_on_non_windows_returns_false(self) -> None:
        """Pasting on non-Windows returns False."""
        from elivroimagine.clipboard import Paster

        paster = Paster()
        result = paster.paste_text("test")
        assert result is False

    @patch.object(sys, "platform", "win32")
    def test_paste_calls_clipboard_and_simulate(self) -> None:
        """Paste sets clipboard and simulates Ctrl+V."""
        from elivroimagine.clipboard import Paster

        paster = Paster()

        with patch.object(paster, "_set_clipboard_with_retry", return_value=True) as mock_set:
            with patch.object(paster, "_get_clipboard", return_value="test text"):
                with patch.object(paster, "_simulate_ctrl_v") as mock_simulate:
                    result = paster.paste_text("test text")

                    assert result is True
                    mock_set.assert_called_once_with("test text")
                    mock_simulate.assert_called_once()

    @patch.object(sys, "platform", "win32")
    def test_paste_restores_clipboard_when_enabled(self) -> None:
        """Paste restores clipboard when restore_clipboard is True."""
        from elivroimagine.clipboard import Paster

        paster = Paster(restore_clipboard=True)

        with patch.object(paster, "_get_clipboard", return_value="original") as mock_get:
            with patch.object(paster, "_set_clipboard_with_retry", return_value=True):
                with patch.object(paster, "_set_clipboard") as mock_set:
                    with patch.object(paster, "_simulate_ctrl_v"):
                        paster.paste_text("new text")

                        # Should have called _get_clipboard to save original
                        mock_get.assert_called()
                        # Should have called _set_clipboard to restore
                        mock_set.assert_called_with("original")

    @patch.object(sys, "platform", "win32")
    def test_paste_no_restore_when_disabled(self) -> None:
        """Paste does not restore clipboard when restore_clipboard is False."""
        from elivroimagine.clipboard import Paster

        paster = Paster(restore_clipboard=False)

        with patch.object(paster, "_set_clipboard_with_retry", return_value=True):
            with patch.object(paster, "_get_clipboard", return_value="new text"):
                with patch.object(paster, "_set_clipboard") as mock_set:
                    with patch.object(paster, "_simulate_ctrl_v"):
                        paster.paste_text("new text")

                        # Should not have called _set_clipboard to restore
                        mock_set.assert_not_called()

    @patch.object(sys, "platform", "win32")
    def test_paste_fails_when_set_clipboard_fails(self) -> None:
        """Paste returns False when clipboard cannot be set."""
        from elivroimagine.clipboard import Paster

        paster = Paster()

        with patch.object(paster, "_set_clipboard_with_retry", return_value=False):
            result = paster.paste_text("test")
            assert result is False

    @patch.object(sys, "platform", "win32")
    def test_paste_fails_when_verification_fails(self) -> None:
        """Paste returns False when clipboard verification fails."""
        from elivroimagine.clipboard import Paster

        paster = Paster()

        with patch.object(paster, "_set_clipboard_with_retry", return_value=True):
            with patch.object(paster, "_get_clipboard", return_value="wrong text"):
                result = paster.paste_text("test text")
                assert result is False


class TestPasterSimulateCtrlV:
    """Tests for Ctrl+V simulation."""

    @patch.object(sys, "platform", "win32")
    def test_simulate_ctrl_v_uses_sendinput(self) -> None:
        """Simulate Ctrl+V uses SendInput API."""
        from elivroimagine.clipboard import Paster

        paster = Paster()

        # Mock the ctypes calls
        with patch("ctypes.windll") as mock_windll:
            mock_user32 = MagicMock()
            mock_windll.user32 = mock_user32
            mock_user32.SendInput.return_value = 4

            paster._simulate_ctrl_v()

            # Verify SendInput was called with 4 inputs
            mock_user32.SendInput.assert_called_once()
            args = mock_user32.SendInput.call_args[0]
            assert args[0] == 4  # 4 key events


class TestPasterClipboard:
    """Tests for clipboard operations."""

    @patch.object(sys, "platform", "win32")
    def test_set_clipboard_with_retry_retries_on_failure(self) -> None:
        """Set clipboard retries on failure."""
        from elivroimagine.clipboard import Paster

        paster = Paster()

        # First two calls fail, third succeeds
        call_count = [0]

        def mock_set_clipboard(text: str) -> bool:
            call_count[0] += 1
            return call_count[0] >= 3

        with patch.object(paster, "_set_clipboard", side_effect=mock_set_clipboard):
            with patch("time.sleep"):  # Don't actually sleep
                result = paster._set_clipboard_with_retry("test", max_retries=3)
                assert result is True
                assert call_count[0] == 3

"""Tests for the Transcriber module (faster-whisper backend)."""

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from elivroimagine.config import TranscriptionConfig, WhisperConfig
from elivroimagine.transcriber import (
    APIError,
    APIKeyMissingError,
    BergetTranscriber,
    LocalTranscriber,
    Transcriber,
    TranscriptionError,
    TranscriptionTimeoutError,
)


class TestTranscriberLazyLoading:
    """Tests for lazy model loading behavior."""

    def test_lazy_model_loading(self, mock_faster_whisper: MagicMock) -> None:
        """Model should not load until transcribe is called."""
        config = WhisperConfig(model_size="tiny")
        transcriber = Transcriber(config)

        # Model should not be loaded yet (access via backend)
        assert isinstance(transcriber._backend, LocalTranscriber)
        assert transcriber._backend._model is None
        mock_faster_whisper.assert_not_called()

        # Trigger model load via transcribe
        audio = np.zeros(16000, dtype=np.float32)
        transcriber.transcribe(audio)

        # Now model should be loaded
        mock_faster_whisper.assert_called_once()

    def test_model_reloads_on_size_change(self, mock_faster_whisper: MagicMock) -> None:
        """Model should reload when size changes."""
        config = WhisperConfig(model_size="tiny")
        transcriber = Transcriber(config)

        audio = np.zeros(16000, dtype=np.float32)

        # First transcription loads tiny model
        transcriber.transcribe(audio)
        assert mock_faster_whisper.call_count == 1
        first_call_args = mock_faster_whisper.call_args
        assert first_call_args[0][0] == "tiny"

        # Change to small model
        transcriber.update_config(WhisperConfig(model_size="small"))
        transcriber.transcribe(audio)

        # Should reload with new size
        assert mock_faster_whisper.call_count == 2
        second_call_args = mock_faster_whisper.call_args
        assert second_call_args[0][0] == "small"


class TestTranscriberNormalization:
    """Tests for audio normalization."""

    def test_transcribe_normalizes_audio(self, mock_faster_whisper: MagicMock) -> None:
        """Audio with values > 1.0 should be normalized."""
        config = WhisperConfig(model_size="tiny")
        transcriber = Transcriber(config)

        # Create audio with values outside [-1, 1] range
        audio = np.array([0, 2.0, -2.0, 1.0, -1.0], dtype=np.float32)

        transcriber.transcribe(audio)

        call_args = mock_faster_whisper.return_value.transcribe.call_args
        normalized_audio = call_args[0][0]

        # All values should be in [-1, 1] range
        assert normalized_audio.max() <= 1.0
        assert normalized_audio.min() >= -1.0

    def test_already_normalized_audio_unchanged(self, mock_faster_whisper: MagicMock) -> None:
        """Audio already in [-1, 1] range should not be modified."""
        config = WhisperConfig(model_size="tiny")
        transcriber = Transcriber(config)

        audio = np.array([0, 0.5, -0.5, 0.8, -0.8], dtype=np.float32)
        original_audio = audio.copy()

        transcriber.transcribe(audio)

        call_args = mock_faster_whisper.return_value.transcribe.call_args
        transcribed_audio = call_args[0][0]

        # Values should be unchanged
        np.testing.assert_array_almost_equal(transcribed_audio, original_audio)


class TestDeviceDetection:
    """Tests for device detection."""

    def test_device_selection_cpu_fallback(self) -> None:
        """_get_device_and_compute should fall back to CPU when CUDA unavailable."""
        config = WhisperConfig(model_size="tiny")
        local_transcriber = LocalTranscriber(config)

        # Mock ctranslate2 to raise ImportError (no CUDA)
        with patch.dict("sys.modules", {"ctranslate2": None}):
            device, compute = local_transcriber._get_device_and_compute()
            assert device == "cpu"
            assert compute == "int8"

    def test_device_selection_cuda_when_available(self) -> None:
        """_get_device_and_compute should use CUDA when available."""
        config = WhisperConfig(model_size="tiny")
        local_transcriber = LocalTranscriber(config)

        mock_ct2 = MagicMock()
        mock_ct2.get_supported_compute_types.return_value = ["float16", "float32", "int8"]

        with patch.dict("sys.modules", {"ctranslate2": mock_ct2}):
            device, compute = local_transcriber._get_device_and_compute()
            assert device == "cuda"
            assert compute == "float16"


class TestCudaFallback:
    """Tests for CUDA-to-CPU fallback when GPU libs are missing."""

    def test_cuda_load_failure_falls_back_to_cpu(
        self, mock_faster_whisper: MagicMock
    ) -> None:
        """Model should retry on CPU when CUDA load raises (e.g. missing cublas DLL)."""
        config = WhisperConfig(model_size="tiny")
        transcriber = Transcriber(config)

        # Access the local backend
        local_backend = transcriber._backend
        assert isinstance(local_backend, LocalTranscriber)

        # Make _get_device_and_compute return cuda
        with patch.object(
            local_backend, "_get_device_and_compute", return_value=("cuda", "float16")
        ):
            # First call (cuda) raises, second call (cpu) succeeds
            mock_model = MagicMock()
            mock_model.transcribe.return_value = (iter([]), MagicMock())
            mock_faster_whisper.side_effect = [
                OSError("cublas64_12.dll is not found"),
                mock_model,
            ]

            audio = np.zeros(16000, dtype=np.float32)
            transcriber.transcribe(audio)

            # Should have been called twice: once for cuda, once for cpu
            assert mock_faster_whisper.call_count == 2
            first_call = mock_faster_whisper.call_args_list[0]
            second_call = mock_faster_whisper.call_args_list[1]
            assert first_call[1]["device"] == "cuda"
            assert second_call[1]["device"] == "cpu"
            assert second_call[1]["compute_type"] == "int8"

    def test_cpu_load_failure_still_raises(
        self, mock_faster_whisper: MagicMock
    ) -> None:
        """When device is already cpu, load failure should not be caught."""
        config = WhisperConfig(model_size="tiny")
        transcriber = Transcriber(config)

        # Access the local backend
        local_backend = transcriber._backend
        assert isinstance(local_backend, LocalTranscriber)

        with patch.object(
            local_backend, "_get_device_and_compute", return_value=("cpu", "int8")
        ):
            mock_faster_whisper.side_effect = RuntimeError("Out of memory")

            audio = np.zeros(16000, dtype=np.float32)
            with pytest.raises(TranscriptionError) as exc_info:
                transcriber.transcribe(audio)

            assert "Failed to load Whisper model" in str(exc_info.value)


class TestCudaInferenceFallback:
    """Tests for CUDA fallback when inference fails (not model load)."""

    def test_cuda_inference_failure_reloads_on_cpu(
        self, mock_faster_whisper: MagicMock
    ) -> None:
        """When CUDA model loads but inference fails with cublas error, reload on CPU and retry."""
        config = WhisperConfig(model_size="tiny")
        transcriber = Transcriber(config)

        # Access the local backend
        local_backend = transcriber._backend
        assert isinstance(local_backend, LocalTranscriber)

        with patch.object(
            local_backend, "_get_device_and_compute", return_value=("cuda", "float16")
        ):
            # First WhisperModel() call succeeds (CUDA model loads fine)
            cuda_model = MagicMock()
            cuda_model.transcribe.side_effect = OSError(
                "Library cublas64_12.dll is not found or cannot be loaded"
            )

            # Second WhisperModel() call is the CPU reload
            cpu_model = MagicMock()
            cpu_model.transcribe.return_value = (iter([]), MagicMock())

            mock_faster_whisper.side_effect = [cuda_model, cpu_model]

            audio = np.zeros(16000, dtype=np.float32)
            transcriber.transcribe(audio)

            # Model was constructed twice: once for CUDA, once for CPU fallback
            assert mock_faster_whisper.call_count == 2
            cpu_call = mock_faster_whisper.call_args_list[1]
            assert cpu_call[1]["device"] == "cpu"
            assert cpu_call[1]["compute_type"] == "int8"

    def test_non_cuda_inference_error_not_retried(
        self, mock_faster_whisper: MagicMock
    ) -> None:
        """Non-CUDA inference errors should not trigger a CPU reload."""
        config = WhisperConfig(model_size="tiny")
        transcriber = Transcriber(config)

        mock_model = MagicMock()
        mock_model.transcribe.side_effect = RuntimeError("some other error")
        mock_faster_whisper.return_value = mock_model

        audio = np.zeros(16000, dtype=np.float32)
        with pytest.raises(TranscriptionError) as exc_info:
            transcriber.transcribe(audio)

        assert "some other error" in str(exc_info.value)
        # Model should only have been constructed once (no CPU reload)
        assert mock_faster_whisper.call_count == 1


class TestLanguageSupport:
    """Tests for language support."""

    def test_transcribe_with_english(self, mock_faster_whisper: MagicMock) -> None:
        """Transcription passes English language to model."""
        config = WhisperConfig(model_size="tiny", language="en")
        transcriber = Transcriber(config)

        audio = np.zeros(16000, dtype=np.float32)
        transcriber.transcribe(audio)

        call_args = mock_faster_whisper.return_value.transcribe.call_args
        assert call_args[1]["language"] == "en"

    def test_transcribe_with_swedish(self, mock_faster_whisper: MagicMock) -> None:
        """Transcription passes Swedish language to model."""
        config = WhisperConfig(model_size="tiny", language="sv")
        transcriber = Transcriber(config)

        audio = np.zeros(16000, dtype=np.float32)
        transcriber.transcribe(audio)

        call_args = mock_faster_whisper.return_value.transcribe.call_args
        assert call_args[1]["language"] == "sv"

    def test_transcribe_auto_detect_omits_language(self, mock_faster_whisper: MagicMock) -> None:
        """Auto-detect should not pass language parameter to model."""
        config = WhisperConfig(model_size="tiny", language="auto")
        transcriber = Transcriber(config)

        audio = np.zeros(16000, dtype=np.float32)
        transcriber.transcribe(audio)

        call_args = mock_faster_whisper.return_value.transcribe.call_args
        # Language should NOT be in kwargs when auto-detect is used
        assert "language" not in call_args[1]

    def test_get_available_languages(self) -> None:
        """get_available_languages returns auto-detect, English and Swedish."""
        langs = Transcriber.get_available_languages()
        lang_codes = [code for code, _ in langs]
        assert "auto" in lang_codes
        assert "en" in lang_codes
        assert "sv" in lang_codes


class TestTimeout:
    """Tests for transcription timeout."""

    @pytest.mark.timeout(10)
    def test_timeout_raises_timeout_error(self, mock_faster_whisper: MagicMock) -> None:
        """Transcription that exceeds timeout raises TranscriptionTimeoutError."""
        import threading

        config = WhisperConfig(model_size="tiny", transcription_timeout_seconds=10)
        transcriber = Transcriber(config)

        # Use an event so the thread can be unblocked after the test
        block_event = threading.Event()

        def slow_transcribe(*args, **kwargs):
            block_event.wait(timeout=10)
            return ([], MagicMock())

        mock_faster_whisper.return_value.transcribe.side_effect = slow_transcribe

        audio = np.zeros(16000, dtype=np.float32)

        # Use a very short timeout for the test
        transcriber.config.transcription_timeout_seconds = 1

        with pytest.raises(TranscriptionTimeoutError):
            transcriber.transcribe(audio)

        # Unblock the background thread so it can clean up
        block_event.set()


class TestErrorHandling:
    """Tests for error handling."""

    def test_transcription_error_on_model_failure(self, mock_faster_whisper: MagicMock) -> None:
        """TranscriptionError should be raised when model fails."""
        config = WhisperConfig(model_size="tiny")
        transcriber = Transcriber(config)

        # Make the model's transcribe method raise an exception
        mock_faster_whisper.return_value.transcribe.side_effect = RuntimeError(
            "Model inference failed"
        )

        audio = np.zeros(16000, dtype=np.float32)

        with pytest.raises(TranscriptionError) as exc_info:
            transcriber.transcribe(audio)

        assert "Failed to transcribe audio" in str(exc_info.value)

    def test_transcription_error_on_load_failure(self, mock_faster_whisper: MagicMock) -> None:
        """TranscriptionError should be raised when model loading fails."""
        config = WhisperConfig(model_size="tiny")
        transcriber = Transcriber(config)

        mock_faster_whisper.side_effect = RuntimeError("Failed to load model")

        audio = np.zeros(16000, dtype=np.float32)

        with pytest.raises(TranscriptionError) as exc_info:
            transcriber.transcribe(audio)

        assert "Failed to load Whisper model" in str(exc_info.value)


class TestModelInfo:
    """Tests for model information methods."""

    def test_get_available_models_includes_large(self) -> None:
        """get_available_models should include 'large' option."""
        models = Transcriber.get_available_models()
        assert "large" in models
        assert models == ["tiny", "base", "small", "medium", "large"]

    def test_get_model_info_large(self) -> None:
        """get_model_info should return info for 'large' model."""
        info = Transcriber.get_model_info("large")
        assert info["size"] == "~1.5GB"
        assert info["vram"] == "~10GB"
        assert info["speed"] == "Slowest"

    def test_get_model_info_all_sizes(self) -> None:
        """get_model_info should return valid info for all model sizes."""
        for model_size in Transcriber.get_available_models():
            info = Transcriber.get_model_info(model_size)  # type: ignore
            assert "size" in info
            assert "vram" in info
            assert "speed" in info
            assert info["size"] != "Unknown"


class TestProgressCallback:
    """Tests for model loading progress callback."""

    def test_progress_callback_called_on_load(self, mock_faster_whisper: MagicMock) -> None:
        """Progress callback is invoked during model loading."""
        progress_messages: list[str] = []

        config = WhisperConfig(model_size="tiny")
        transcriber = Transcriber(config, on_progress=lambda msg: progress_messages.append(msg))

        audio = np.zeros(16000, dtype=np.float32)
        transcriber.transcribe(audio)

        assert len(progress_messages) >= 2
        assert any("Loading" in msg for msg in progress_messages)
        assert any("ready" in msg for msg in progress_messages)

    def test_no_progress_callback_is_fine(self, mock_faster_whisper: MagicMock) -> None:
        """Transcription works without a progress callback."""
        config = WhisperConfig(model_size="tiny")
        transcriber = Transcriber(config)

        audio = np.zeros(16000, dtype=np.float32)
        result = transcriber.transcribe(audio)

        assert result == "Test transcription"


class TestBackendSwitching:
    """Tests for backend switching behavior."""

    def test_default_backend_is_local(self, mock_faster_whisper: MagicMock) -> None:
        """Default backend should be local."""
        config = WhisperConfig(model_size="tiny")
        transcriber = Transcriber(config)

        assert isinstance(transcriber._backend, LocalTranscriber)

    def test_berget_backend_when_configured(self) -> None:
        """Berget backend should be used when configured."""
        config = WhisperConfig(model_size="tiny")
        trans_config = TranscriptionConfig(backend="berget", berget_api_key="test-key")
        transcriber = Transcriber(config, transcription_config=trans_config)

        assert isinstance(transcriber._backend, BergetTranscriber)

    def test_update_transcription_config_switches_backend(
        self, mock_faster_whisper: MagicMock
    ) -> None:
        """Updating transcription config should switch backend."""
        config = WhisperConfig(model_size="tiny")
        transcriber = Transcriber(config)

        # Start with local
        assert isinstance(transcriber._backend, LocalTranscriber)

        # Switch to berget
        new_config = TranscriptionConfig(backend="berget", berget_api_key="test-key")
        transcriber.update_transcription_config(new_config)

        assert isinstance(transcriber._backend, BergetTranscriber)

    def test_update_transcription_config_updates_api_key(self) -> None:
        """Updating transcription config should update API key without recreating backend."""
        config = WhisperConfig(model_size="tiny")
        trans_config = TranscriptionConfig(backend="berget", berget_api_key="old-key")
        transcriber = Transcriber(config, transcription_config=trans_config)

        old_backend = transcriber._backend

        # Update API key only
        new_config = TranscriptionConfig(backend="berget", berget_api_key="new-key")
        transcriber.update_transcription_config(new_config)

        # Should be same backend instance
        assert transcriber._backend is old_backend
        # API key should be updated
        assert transcriber._backend.api_key == "new-key"


class TestBergetTranscriber:
    """Tests for Berget.ai API transcriber."""

    def test_missing_api_key_raises_error(self) -> None:
        """Transcription without API key should raise APIKeyMissingError."""
        config = WhisperConfig(model_size="tiny")
        transcriber = BergetTranscriber(api_key="", config=config)

        audio = np.zeros(16000, dtype=np.float32)

        with pytest.raises(APIKeyMissingError) as exc_info:
            transcriber.transcribe(audio)

        assert "API key not configured" in str(exc_info.value)

    def test_audio_to_wav_bytes_produces_valid_wav(self) -> None:
        """_audio_to_wav_bytes should produce valid WAV data."""
        config = WhisperConfig(model_size="tiny")
        transcriber = BergetTranscriber(api_key="test", config=config)

        # Create simple audio
        audio = np.array([0.0, 0.5, -0.5, 1.0, -1.0], dtype=np.float32)
        wav_bytes = transcriber._audio_to_wav_bytes(audio, 16000)

        # Check WAV header
        assert wav_bytes[:4] == b"RIFF"
        assert wav_bytes[8:12] == b"WAVE"

    def test_api_call_with_mocked_requests(self) -> None:
        """Test API call with mocked requests."""
        config = WhisperConfig(model_size="tiny", language="en")
        transcriber = BergetTranscriber(api_key="test-api-key", config=config)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"text": "Hello world"}

        with patch("requests.post", return_value=mock_response) as mock_post:
            audio = np.zeros(16000, dtype=np.float32)
            result = transcriber.transcribe(audio)

            assert result == "Hello world"
            mock_post.assert_called_once()

            # Verify API call parameters
            call_kwargs = mock_post.call_args[1]
            assert call_kwargs["headers"]["Authorization"] == "Bearer test-api-key"
            assert call_kwargs["data"]["model"] == "KBLab/kb-whisper-large"
            assert call_kwargs["data"]["language"] == "en"

    def test_api_call_auto_detect_omits_language(self) -> None:
        """Auto-detect should omit language parameter from API call."""
        config = WhisperConfig(model_size="tiny", language="auto")
        transcriber = BergetTranscriber(api_key="test-api-key", config=config)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"text": "Hello world"}

        with patch("requests.post", return_value=mock_response) as mock_post:
            audio = np.zeros(16000, dtype=np.float32)
            transcriber.transcribe(audio)

            # Verify language is NOT in the data
            call_kwargs = mock_post.call_args[1]
            assert "language" not in call_kwargs["data"]
            assert call_kwargs["data"]["model"] == "KBLab/kb-whisper-large"

    def test_api_401_raises_api_error(self) -> None:
        """401 response should raise APIError with invalid key message."""
        config = WhisperConfig(model_size="tiny")
        transcriber = BergetTranscriber(api_key="bad-key", config=config)

        mock_response = MagicMock()
        mock_response.status_code = 401

        with patch("requests.post", return_value=mock_response):
            audio = np.zeros(16000, dtype=np.float32)

            with pytest.raises(APIError) as exc_info:
                transcriber.transcribe(audio)

            assert "Invalid" in str(exc_info.value)

    def test_api_429_raises_api_error(self) -> None:
        """429 response should raise APIError with rate limit message."""
        config = WhisperConfig(model_size="tiny")
        transcriber = BergetTranscriber(api_key="test-key", config=config)

        mock_response = MagicMock()
        mock_response.status_code = 429

        with patch("requests.post", return_value=mock_response):
            audio = np.zeros(16000, dtype=np.float32)

            with pytest.raises(APIError) as exc_info:
                transcriber.transcribe(audio)

            assert "rate limit" in str(exc_info.value)

    def test_api_timeout_raises_timeout_error(self) -> None:
        """Request timeout should raise TranscriptionTimeoutError."""
        import requests

        config = WhisperConfig(model_size="tiny", transcription_timeout_seconds=10)
        transcriber = BergetTranscriber(api_key="test-key", config=config)

        with patch("requests.post", side_effect=requests.Timeout()):
            audio = np.zeros(16000, dtype=np.float32)

            with pytest.raises(TranscriptionTimeoutError):
                transcriber.transcribe(audio)

    def test_connection_error_raises_api_error(self) -> None:
        """Connection error should raise APIError."""
        import requests

        config = WhisperConfig(model_size="tiny")
        transcriber = BergetTranscriber(api_key="test-key", config=config)

        with patch("requests.post", side_effect=requests.ConnectionError()):
            audio = np.zeros(16000, dtype=np.float32)

            with pytest.raises(APIError) as exc_info:
                transcriber.transcribe(audio)

            assert "connect" in str(exc_info.value).lower()

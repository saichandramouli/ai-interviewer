from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from integrations.speech.base import STTResult, AudioValidationError, STTError


class BaseSTTProvider(ABC):
    """
    Abstract interface for Speech-to-Text providers.
    Enforces format validation, size constraints, and standardized output.
    """

    MAX_AUDIO_BYTES = 25 * 1024 * 1024  # 25 MB max per turn
    SUPPORTED_CONTENT_TYPES = {
        "audio/wav",
        "audio/x-wav",
        "audio/webm",
        "audio/ogg",
        "audio/mp3",
        "audio/mpeg",
        "audio/m4a",
        "audio/x-m4a",
    }

    def __init__(self, provider_name: str):
        self.provider_name = provider_name

    def validate_audio(self, audio_bytes: bytes, content_type: str):
        """
        Validates input audio bytes and MIME content type.
        """
        if not audio_bytes or len(audio_bytes) == 0:
            raise AudioValidationError("Audio data is empty.", error_code="EMPTY_AUDIO")

        if len(audio_bytes) > self.MAX_AUDIO_BYTES:
            raise AudioValidationError(
                f"Audio payload size ({len(audio_bytes)} bytes) exceeds max limit of {self.MAX_AUDIO_BYTES} bytes (25MB).",
                error_code="AUDIO_TOO_LARGE"
            )

        normalized_type = (content_type or "").lower().split(";")[0].strip()
        if normalized_type not in self.SUPPORTED_CONTENT_TYPES:
            raise AudioValidationError(
                f"Unsupported audio format '{content_type}'. Supported formats: {sorted(list(self.SUPPORTED_CONTENT_TYPES))}",
                error_code="UNSUPPORTED_AUDIO_FORMAT"
            )

    @abstractmethod
    def transcribe(
        self,
        audio_bytes: bytes,
        content_type: str = "audio/wav",
        language: str = "en-IN",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> STTResult:
        """
        Transcribes candidate audio into text.
        """
        pass


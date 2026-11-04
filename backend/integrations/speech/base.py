from dataclasses import dataclass
from typing import Optional, Dict, Any


class SpeechError(Exception):
    """Base exception for speech operations."""
    def __init__(self, message: str, error_code: str = "SPEECH_ERROR"):
        super().__init__(message)
        self.error_code = error_code


class STTError(SpeechError):
    """Base exception for Speech-to-Text operations."""
    def __init__(self, message: str, error_code: str = "STT_ERROR"):
        super().__init__(message, error_code=error_code)


class TTSError(SpeechError):
    """Base exception for Text-to-Speech operations."""
    def __init__(self, message: str, error_code: str = "TTS_ERROR"):
        super().__init__(message, error_code=error_code)


class AudioValidationError(SpeechError):
    """Raised when audio payload fails format, size, or integrity checks."""
    def __init__(self, message: str, error_code: str = "AUDIO_VALIDATION_ERROR"):
        super().__init__(message, error_code=error_code)


class ProviderTimeoutError(SpeechError):
    """Raised when remote speech provider times out."""
    def __init__(self, message: str, error_code: str = "PROVIDER_TIMEOUT"):
        super().__init__(message, error_code=error_code)


class ProviderRateLimitError(SpeechError):
    """Raised when speech provider returns rate limit (429)."""
    def __init__(self, message: str, error_code: str = "PROVIDER_RATE_LIMIT"):
        super().__init__(message, error_code=error_code)


@dataclass
class STTResult:
    """Standardized output of speech recognition."""
    text: str
    confidence: float
    duration_seconds: float
    is_empty: bool
    provider_name: str
    metadata: Dict[str, Any]


@dataclass
class TTSResult:
    """Standardized output of speech synthesis."""
    audio_bytes: bytes
    audio_format: str
    sample_rate: int
    duration_seconds: float
    provider_name: str
    metadata: Dict[str, Any]


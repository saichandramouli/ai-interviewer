from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from integrations.speech.base import TTSResult, AudioValidationError, TTSError


class BaseTTSProvider(ABC):
    """
    Abstract interface for Text-to-Speech providers.
    Enforces strict message hygiene and validation.
    """

    MAX_TEXT_CHARACTERS = 4000  # Enforce reasonable length limit per spoken turn

    def __init__(self, provider_name: str):
        self.provider_name = provider_name

    def validate_text(self, text: str):
        """
        Validates spoken message text to prevent synthesizing empty strings
        or oversized payloads.
        """
        if not text or not text.strip():
            raise AudioValidationError(
                "Interviewer message text cannot be empty for speech synthesis.",
                error_code="EMPTY_TEXT"
            )

        if len(text) > self.MAX_TEXT_CHARACTERS:
            raise AudioValidationError(
                f"Text length ({len(text)} characters) exceeds max limit of {self.MAX_TEXT_CHARACTERS}.",
                error_code="TEXT_TOO_LONG"
            )

    @abstractmethod
    def synthesize(
        self,
        text: str,
        voice_id: Optional[str] = None,
        language: str = "en-IN",
        output_format: str = "audio/wav",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> TTSResult:
        """
        Synthesizes candidate-facing text into speech audio bytes.
        """
        pass


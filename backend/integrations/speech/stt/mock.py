import logging
from typing import Optional, Dict, Any
from integrations.speech.stt.base import BaseSTTProvider
from integrations.speech.base import STTResult

logger = logging.getLogger(__name__)


class MockSTTProvider(BaseSTTProvider):
    """
    Deterministic mock STT provider for unit tests and local simulation.
    Never initiates external HTTP or network requests.
    """

    def __init__(self, default_transcript: str = "This is a deterministic mock candidate response."):
        super().__init__(provider_name="mock_stt")
        self.default_transcript = default_transcript
        self.call_count = 0

    def transcribe(
        self,
        audio_bytes: bytes,
        content_type: str = "audio/wav",
        language: str = "en-IN",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> STTResult:
        # Validate audio format & size
        self.validate_audio(audio_bytes, content_type)
        self.call_count += 1

        meta = metadata or {}
        # If simulated_text was passed in metadata (e.g. from test fixture), prefer it
        transcript = meta.get("simulated_text", self.default_transcript)
        is_silence = meta.get("simulate_silence", False)

        if is_silence:
            return STTResult(
                text="",
                confidence=0.0,
                duration_seconds=float(len(audio_bytes) / 32000.0),
                is_empty=True,
                provider_name=self.provider_name,
                metadata={"is_mock": True, "call_count": self.call_count, "silence": True},
            )

        return STTResult(
            text=transcript,
            confidence=0.98,
            duration_seconds=float(len(audio_bytes) / 32000.0),
            is_empty=(len(transcript.strip()) == 0),
            provider_name=self.provider_name,
            metadata={"is_mock": True, "call_count": self.call_count, "language": language},
        )


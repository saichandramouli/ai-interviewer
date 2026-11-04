import logging
from typing import Optional, Dict, Any
from integrations.speech.tts.base import BaseTTSProvider
from integrations.speech.base import TTSResult

logger = logging.getLogger(__name__)


class MockTTSProvider(BaseTTSProvider):
    """
    Deterministic mock TTS provider for unit tests and local simulation.
    Generates synthetic valid WAV header + PCM audio bytes.
    """

    # Minimal valid 44-byte WAV header for 16kHz Mono 16-bit PCM
    MOCK_WAV_BYTES = (
        b"RIFF\x2c\x00\x00\x00WAVEfmt \x10\x00\x00\x00"
        b"\x01\x00\x01\x00\x80>\x00\x00\x00}\x00\x00"
        b"\x02\x00\x10\x00data\x08\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
    )

    def __init__(self, default_voice: str = "mock-en-in-professional"):
        super().__init__(provider_name="mock_tts")
        self.default_voice = default_voice
        self.call_count = 0

    def synthesize(
        self,
        text: str,
        voice_id: Optional[str] = None,
        language: str = "en-IN",
        output_format: str = "audio/wav",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> TTSResult:
        self.validate_text(text)
        self.call_count += 1

        # Simulate ~15 chars per second of spoken speech
        simulated_duration = max(1.0, round(len(text) / 15.0, 2))

        return TTSResult(
            audio_bytes=self.MOCK_WAV_BYTES,
            audio_format="audio/wav",
            sample_rate=16000,
            duration_seconds=simulated_duration,
            provider_name=self.provider_name,
            metadata={
                "is_mock": True,
                "call_count": self.call_count,
                "voice_id": voice_id or self.default_voice,
                "language": language,
                "char_length": len(text),
            },
        )


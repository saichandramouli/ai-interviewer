import os
import json
import logging
from typing import Optional, Dict, Any
import requests

from integrations.speech.tts.base import BaseTTSProvider
from integrations.speech.base import (
    TTSResult,
    TTSError,
    ProviderTimeoutError,
    ProviderRateLimitError,
)

logger = logging.getLogger(__name__)


class ElevenLabsTTSProvider(BaseTTSProvider):
    """
    Production-grade Text-to-Speech provider implementing ElevenLabs hosted API.
    Supports Eleven Multilingual v2 / Flash models with natural Indian English accents,
    professional voice timbre, and high-fidelity output.
    """

    DEFAULT_BASE_URL = "https://api.elevenlabs.io/v1/text-to-speech"
    DEFAULT_VOICE_ID = "21m00Tcm4TlvDq8ikWAM"  # Standard default voice (Rachel)
    DEFAULT_MODEL_ID = "eleven_multilingual_v2"
    DEFAULT_TIMEOUT_SECONDS = 30.0

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        default_voice_id: Optional[str] = None,
        model_id: Optional[str] = None,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ):
        super().__init__(provider_name="elevenlabs")
        raw_key = api_key or os.getenv("ELEVENLABS_API_KEY", os.getenv("TTS_API_KEY", ""))
        self.api_key = raw_key.strip("\"' \t\r\n") if raw_key else ""
        self.base_url = (base_url or os.getenv("ELEVENLABS_BASE_URL", os.getenv("TTS_BASE_URL", self.DEFAULT_BASE_URL))).rstrip("/")
        self.default_voice_id = default_voice_id or os.getenv("ELEVENLABS_VOICE_ID", self.DEFAULT_VOICE_ID)
        self.model_id = model_id or os.getenv("ELEVENLABS_MODEL_ID", self.DEFAULT_MODEL_ID)
        self.timeout = timeout
        self.session = requests.Session()

    def synthesize(
        self,
        text: str,
        voice_id: Optional[str] = None,
        language: str = "en-IN",
        output_format: str = "audio/wav",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> TTSResult:
        # Step 1: Pre-flight text validation
        self.validate_text(text)

        if not self.api_key:
            raise TTSError("ElevenLabs API key is not configured.", error_code="TTS_AUTH_MISSING")

        target_voice = voice_id or self.default_voice_id
        endpoint = f"{self.base_url}/{target_voice}"

        headers = {
            "xi-api-key": self.api_key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        }

        payload = {
            "text": text,
            "model_id": self.model_id,
            "voice_settings": {
                "stability": 0.50,
                "similarity_boost": 0.75,
            },
        }

        try:
            response = self.session.post(
                endpoint,
                headers=headers,
                json=payload,
                timeout=self.timeout,
            )

            if response.status_code == 429:
                raise ProviderRateLimitError(
                    "ElevenLabs API rate limit reached. Please throttle requests.",
                    error_code="TTS_RATE_LIMIT"
                )

            if response.status_code == 401 or response.status_code == 403:
                raise TTSError(
                    "ElevenLabs API authentication failed. Verify API credentials.",
                    error_code="TTS_AUTH_FAILED"
                )

            if response.status_code != 200:
                raise TTSError(
                    f"ElevenLabs synthesis failed with status {response.status_code}.",
                    error_code=f"TTS_HTTP_{response.status_code}"
                )

            audio_data = response.content
            if not audio_data:
                raise TTSError("ElevenLabs returned empty audio payload.", error_code="TTS_EMPTY_PAYLOAD")

            # Calculate approximate duration based on text length (~15 characters per second)
            estimated_duration = max(1.0, round(len(text) / 15.0, 2))

            return TTSResult(
                audio_bytes=audio_data,
                audio_format="audio/mpeg",
                sample_rate=22050,
                duration_seconds=estimated_duration,
                provider_name=self.provider_name,
                metadata={
                    "voice_id": target_voice,
                    "model_id": self.model_id,
                    "language": language,
                    "bytes_received": len(audio_data),
                },
            )

        except requests.exceptions.Timeout:
            raise ProviderTimeoutError(
                f"ElevenLabs synthesis timed out after {self.timeout}s.",
                error_code="TTS_TIMEOUT"
            )
        except requests.exceptions.RequestException as err:
            raise TTSError(
                f"Network error contacting ElevenLabs: {type(err).__name__}",
                error_code="TTS_NETWORK_ERROR"
            )


import os
import json
import logging
from typing import Optional, Dict, Any
import requests

from integrations.speech.stt.base import BaseSTTProvider
from integrations.speech.base import (
    STTResult,
    STTError,
    ProviderTimeoutError,
    ProviderRateLimitError,
)

logger = logging.getLogger(__name__)


class DeepgramSTTProvider(BaseSTTProvider):
    """
    Production-grade Speech-to-Text provider implementing Deepgram's hosted REST API.
    Supports Nova-3 / Nova-2 models with high-accuracy Indian English (en-IN) recognition,
    smart formatting, and low-latency audio transcription.
    """

    DEFAULT_BASE_URL = "https://api.deepgram.com/v1/listen"
    DEFAULT_TIMEOUT_SECONDS = 30.0

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ):
        super().__init__(provider_name="deepgram")
        raw_key = api_key or os.getenv("DEEPGRAM_API_KEY", os.getenv("STT_API_KEY", ""))
        self.api_key = raw_key.strip("\"' \t\r\n") if raw_key else ""
        self.base_url = (base_url or os.getenv("DEEPGRAM_BASE_URL", os.getenv("STT_BASE_URL", self.DEFAULT_BASE_URL)))
        self.model = model or os.getenv("DEEPGRAM_MODEL", "nova-3")
        self.timeout = timeout
        self.session = requests.Session()

    def transcribe(
        self,
        audio_bytes: bytes,
        content_type: str = "audio/wav",
        language: str = "en-IN",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> STTResult:
        # Step 1: Pre-flight payload validation
        self.validate_audio(audio_bytes, content_type)

        if not self.api_key:
            raise STTError("Deepgram API key is not configured.", error_code="STT_AUTH_MISSING")

        normalized_type = (content_type or "audio/wav").lower().split(";")[0].strip()

        headers = {
            "Authorization": f"Token {self.api_key}",
            "Content-Type": normalized_type,
            "Accept": "application/json",
        }

        params = {
            "model": self.model,
            "language": language,
            "smart_format": "true",
            "punctuate": "true",
        }

        try:
            response = self.session.post(
                self.base_url,
                headers=headers,
                params=params,
                data=audio_bytes,
                timeout=self.timeout,
            )

            if response.status_code == 429:
                raise ProviderRateLimitError(
                    "Deepgram API rate limit reached. Please throttle requests.",
                    error_code="STT_RATE_LIMIT"
                )

            if response.status_code == 401 or response.status_code == 403:
                raise STTError(
                    "Deepgram API authentication failed. Verify API credentials.",
                    error_code="STT_AUTH_FAILED"
                )

            if response.status_code != 200:
                raise STTError(
                    f"Deepgram transcription failed with status {response.status_code}.",
                    error_code=f"STT_HTTP_{response.status_code}"
                )

            data = response.json()
            channels = data.get("results", {}).get("channels", [])
            if not channels:
                return STTResult(
                    text="",
                    confidence=0.0,
                    duration_seconds=float(data.get("metadata", {}).get("duration", 0.0)),
                    is_empty=True,
                    provider_name=self.provider_name,
                    metadata={"raw": data.get("metadata", {})},
                )

            alternatives = channels[0].get("alternatives", [])
            if not alternatives:
                return STTResult(
                    text="",
                    confidence=0.0,
                    duration_seconds=float(data.get("metadata", {}).get("duration", 0.0)),
                    is_empty=True,
                    provider_name=self.provider_name,
                    metadata={"raw": data.get("metadata", {})},
                )

            primary = alternatives[0]
            transcript = (primary.get("transcript") or "").strip()
            confidence = float(primary.get("confidence", 0.0))
            duration = float(data.get("metadata", {}).get("duration", 0.0))

            return STTResult(
                text=transcript,
                confidence=confidence,
                duration_seconds=duration,
                is_empty=(len(transcript) == 0),
                provider_name=self.provider_name,
                metadata={"model": self.model, "language": language},
            )

        except requests.exceptions.Timeout:
            raise ProviderTimeoutError(
                f"Deepgram transcription timed out after {self.timeout}s.",
                error_code="STT_TIMEOUT"
            )
        except requests.exceptions.RequestException as err:
            raise STTError(
                f"Network error contacting Deepgram: {type(err).__name__}",
                error_code="STT_NETWORK_ERROR"
            )
        except (ValueError, KeyError) as err:
            raise STTError(
                f"Failed to parse Deepgram response: {str(err)}",
                error_code="STT_PARSE_ERROR"
            )


import os
from typing import Optional
from integrations.speech.stt.base import BaseSTTProvider
from integrations.speech.stt.mock import MockSTTProvider
from integrations.speech.stt.deepgram import DeepgramSTTProvider
from integrations.speech.tts.base import BaseTTSProvider
from integrations.speech.tts.mock import MockTTSProvider
from integrations.speech.tts.elevenlabs import ElevenLabsTTSProvider


class SpeechProviderFactory:
    """
    Central factory for instantiating configured STT and TTS providers.
    Enforces loose coupling and seamless fallback to mock providers.
    """

    @classmethod
    def get_stt_provider(cls, provider_type: Optional[str] = None) -> BaseSTTProvider:
        p_type = (provider_type or os.getenv("STT_PROVIDER", "mock")).lower().strip()
        if p_type == "deepgram":
            return DeepgramSTTProvider()
        return MockSTTProvider()

    @classmethod
    def get_tts_provider(cls, provider_type: Optional[str] = None) -> BaseTTSProvider:
        p_type = (provider_type or os.getenv("TTS_PROVIDER", "mock")).lower().strip()
        if p_type == "elevenlabs":
            return ElevenLabsTTSProvider()
        return MockTTSProvider()


# backend/integrations/voice/__init__.py
from integrations.voice.base import (
    VoiceProvider,
    VoiceProviderError,
    SessionStartResult,
    QuestionDeliveryResult,
    CandidateResponseResult,
    SessionTerminationResult,
)
from integrations.voice.mock_provider import MockVoiceProvider

__all__ = [
    'VoiceProvider',
    'VoiceProviderError',
    'SessionStartResult',
    'QuestionDeliveryResult',
    'CandidateResponseResult',
    'SessionTerminationResult',
    'MockVoiceProvider',
]

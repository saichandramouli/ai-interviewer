from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Dict, Any


class VoiceProviderError(Exception):
    """Base exception for voice provider operations."""
    def __init__(self, message: str, error_code: str = "VOICE_PROVIDER_ERROR"):
        super().__init__(message)
        self.error_code = error_code


class SessionConnectionError(VoiceProviderError):
    """Raised when establishing or maintaining session connection fails."""
    pass


class InvalidSessionStateError(VoiceProviderError):
    """Raised when an operation is invalid for current session state."""
    pass


@dataclass
class SessionStartResult:
    session_id: str
    provider_name: str
    is_mock: bool
    status: str
    metadata: Dict[str, Any]


@dataclass
class QuestionDeliveryResult:
    session_id: str
    sequence_number: int
    question_text: str
    delivered: bool
    is_mock: bool
    metadata: Dict[str, Any]


@dataclass
class CandidateResponseResult:
    session_id: str
    response_text: str
    is_silence: bool
    is_disconnection: bool
    metadata: Dict[str, Any]


@dataclass
class SessionTerminationResult:
    session_id: str
    status: str
    reason: str
    is_mock: bool
    metadata: Dict[str, Any]


class VoiceProvider(ABC):
    """
    Abstract interface for telephony and voice provider integrations.
    Supports starting sessions, question delivery, candidate response receiving,
    interruption/disconnection, and ending sessions.
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Returns the identifier of the voice provider."""
        pass

    @property
    @abstractmethod
    def is_mock(self) -> bool:
        """Flag confirming whether provider operates in simulated mock mode."""
        pass

    @abstractmethod
    def start_session(
        self,
        interview_id: str,
        candidate_phone: str,
        duration_limit_seconds: int,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SessionStartResult:
        """
        Starts or connects a voice session for an interview.
        """
        pass

    @abstractmethod
    def deliver_question(
        self,
        session_id: str,
        sequence_number: int,
        question_text: str,
        is_follow_up: bool = False,
    ) -> QuestionDeliveryResult:
        """
        Synthesizes / delivers the next AI utterance or question to the session.
        """
        pass

    @abstractmethod
    def receive_candidate_response(
        self,
        session_id: str,
        simulated_text: Optional[str] = None,
        simulate_silence: bool = False,
        simulate_disconnect: bool = False,
    ) -> CandidateResponseResult:
        """
        Receives or simulates candidate response from session.
        """
        pass

    @abstractmethod
    def end_session(
        self,
        session_id: str,
        reason: str = "completed",
    ) -> SessionTerminationResult:
        """
        Gracefully terminates or disconnects an active voice session.
        """
        pass

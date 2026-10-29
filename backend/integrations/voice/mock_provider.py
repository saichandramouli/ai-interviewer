import uuid
from typing import Optional, Dict, Any
from integrations.voice.base import (
    VoiceProvider,
    VoiceProviderError,
    SessionConnectionError,
    InvalidSessionStateError,
    SessionStartResult,
    QuestionDeliveryResult,
    CandidateResponseResult,
    SessionTerminationResult,
)


class MockVoiceProvider(VoiceProvider):
    """
    Deterministic mock voice provider implementation for Phase 7 testing.
    Never transmits real audio or contacts external networks.
    """

    def __init__(self, should_fail_start: bool = False, should_fail_delivery: bool = False):
        self.should_fail_start = should_fail_start
        self.should_fail_delivery = should_fail_delivery
        self.active_sessions: Dict[str, Dict[str, Any]] = {}

    @property
    def provider_name(self) -> str:
        return "mock_voice_provider"

    @property
    def is_mock(self) -> bool:
        return True

    def start_session(
        self,
        interview_id: str,
        candidate_phone: str,
        duration_limit_seconds: int,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SessionStartResult:
        if self.should_fail_start:
            raise SessionConnectionError(
                "Mock provider simulated start connection failure.",
                error_code="MOCK_START_FAILED"
            )

        session_id = f"mock-call-{interview_id[:8]}-{uuid.uuid4().hex[:8]}"
        self.active_sessions[session_id] = {
            "interview_id": interview_id,
            "candidate_phone": candidate_phone,
            "duration_limit_seconds": duration_limit_seconds,
            "status": "connected",
            "delivered_questions": [],
        }

        return SessionStartResult(
            session_id=session_id,
            provider_name=self.provider_name,
            is_mock=True,
            status="connected",
            metadata={
                "simulation": True,
                "disclaimer": "Simulated mock session only. No real audio or phone call.",
                "custom_metadata": metadata or {},
            },
        )

    def deliver_question(
        self,
        session_id: str,
        sequence_number: int,
        question_text: str,
        is_follow_up: bool = False,
    ) -> QuestionDeliveryResult:
        session = self.active_sessions.get(session_id)
        if not session and not session_id.startswith("mock-call-"):
            raise InvalidSessionStateError(
                f"Session '{session_id}' not found or already terminated.",
                error_code="SESSION_NOT_FOUND"
            )

        if self.should_fail_delivery:
            raise VoiceProviderError(
                "Mock provider failed to synthesize or deliver question utterance.",
                error_code="DELIVERY_FAILED"
            )

        if session:
            session["delivered_questions"].append({
                "sequence_number": sequence_number,
                "question_text": question_text,
                "is_follow_up": is_follow_up,
            })

        return QuestionDeliveryResult(
            session_id=session_id,
            sequence_number=sequence_number,
            question_text=question_text,
            delivered=True,
            is_mock=True,
            metadata={
                "simulation": True,
                "is_follow_up": is_follow_up,
            },
        )

    def receive_candidate_response(
        self,
        session_id: str,
        simulated_text: Optional[str] = None,
        simulate_silence: bool = False,
        simulate_disconnect: bool = False,
    ) -> CandidateResponseResult:
        if simulate_disconnect:
            if session_id in self.active_sessions:
                self.active_sessions[session_id]["status"] = "disconnected"
            return CandidateResponseResult(
                session_id=session_id,
                response_text="",
                is_silence=False,
                is_disconnection=True,
                metadata={"disconnection_reason": "candidate_hangup"},
            )

        if simulate_silence:
            return CandidateResponseResult(
                session_id=session_id,
                response_text="",
                is_silence=True,
                is_disconnection=False,
                metadata={"silence_duration_seconds": 10},
            )

        response = (simulated_text or "").strip()
        if not response:
            response = "Thank you. I have experience with this in my previous engineering projects."

        return CandidateResponseResult(
            session_id=session_id,
            response_text=response,
            is_silence=False,
            is_disconnection=False,
            metadata={"simulation": True},
        )

    def end_session(
        self,
        session_id: str,
        reason: str = "completed",
    ) -> SessionTerminationResult:
        if session_id in self.active_sessions:
            self.active_sessions[session_id]["status"] = f"ended:{reason}"

        return SessionTerminationResult(
            session_id=session_id,
            status="terminated",
            reason=reason,
            is_mock=True,
            metadata={"simulation": True},
        )

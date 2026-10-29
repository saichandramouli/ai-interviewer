import logging
from typing import Optional, Dict, Any, Tuple
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError

from interviews.models import (
    Interview,
    InterviewQuestion,
    TranscriptEntry,
    InterviewEvent,
    InterviewStatusTransitionError,
)
from candidates.models import Candidate
from integrations.voice.base import VoiceProvider, VoiceProviderError
from integrations.voice.mock_provider import MockVoiceProvider

logger = logging.getLogger(__name__)


class OrchestrationError(Exception):
    """Base exception for interview orchestration errors."""
    def __init__(self, message: str, error_code: str = "ORCHESTRATION_ERROR"):
        super().__init__(message)
        self.error_code = error_code


class ConsentRequiredError(OrchestrationError):
    """Raised when an interview is started without verifiable candidate consent."""
    pass


class PlanRequiredError(OrchestrationError):
    """Raised when an interview has no approved questions or plan."""
    pass


class TimeLimitExceededError(OrchestrationError):
    """Raised when attempting actions after interview time limit has expired."""
    pass


class InterviewOrchestrationService:
    """
    Coordinates interview lifecycle, timing, question progression,
    simulated audio events, transcript persistence, and termination.
    """

    WARNING_THRESHOLD_PERCENT = 80  # Warning threshold at 80% duration elapsed

    def __init__(self, interview: Interview, provider: Optional[VoiceProvider] = None):
        self.interview = interview
        self.provider = provider or MockVoiceProvider()

    def _calculate_timing(self) -> Dict[str, Any]:
        """Calculates elapsed, remaining, and limit seconds based on persisted timestamps."""
        duration_limit = self.interview.duration_limit_seconds or 1800
        started_at = self.interview.started_at

        if not started_at:
            return {
                "elapsed_seconds": 0,
                "remaining_seconds": duration_limit,
                "duration_limit_seconds": duration_limit,
                "is_expired": False,
                "warning_triggered": False,
            }

        now = self.interview.ended_at or timezone.now()
        elapsed = max(0, int((now - started_at).total_seconds()))
        remaining = max(0, duration_limit - elapsed)
        is_expired = elapsed >= duration_limit
        warning_triggered = (elapsed / duration_limit) >= (self.WARNING_THRESHOLD_PERCENT / 100.0)

        return {
            "elapsed_seconds": elapsed,
            "remaining_seconds": remaining,
            "duration_limit_seconds": duration_limit,
            "is_expired": is_expired,
            "warning_triggered": warning_triggered,
        }

    def _verify_preconditions_for_start(self):
        """Validates candidate consent, plan questions, and status rules before start."""
        # 1. State machine transition check
        if self.interview.status not in [Interview.STATUS_DRAFT, Interview.STATUS_SCHEDULED]:
            raise OrchestrationError(
                f"Cannot start interview in status '{self.interview.status}'. Interview must be draft or scheduled.",
                error_code="INVALID_STATUS"
            )

        # 2. Approved plan & questions check
        if not self.interview.questions.exists():
            raise PlanRequiredError(
                "Interview does not have an approved interview plan or questions. Plan generation required.",
                error_code="NO_PLAN_QUESTIONS"
            )

        # 3. Candidate consent check - must be granted and recorded
        candidate = self.interview.candidate
        if candidate.consent_status != Candidate.CONSENT_GRANTED:
            raise ConsentRequiredError(
                f"Candidate consent is '{candidate.consent_status}'. Starting an interview requires granted consent.",
                error_code="CONSENT_NOT_GRANTED"
            )
        if not candidate.consent_recorded_at or not candidate.consent_method:
            raise ConsentRequiredError(
                "Candidate consent record is missing timestamp or verification method. Verifiable audit record required.",
                error_code="CONSENT_UNVERIFIED"
            )

    @transaction.atomic
    def start_interview(self, idempotency_key: Optional[str] = None) -> Dict[str, Any]:
        """
        Transitions interview to calling/in_progress, registers provider session,
        emits AI introduction utterance, and persists transcript.
        """
        # Idempotency check if key provided
        if idempotency_key:
            existing_event = InterviewEvent.objects.filter(
                interview=self.interview,
                idempotency_key=idempotency_key
            ).first()
            if existing_event:
                return self.get_session_state(message="Interview start already processed (idempotent replay).")

        self._verify_preconditions_for_start()

        # Step A: Transition to calling then in_progress
        self.interview.transition_to(Interview.STATUS_CALLING, save=True)

        try:
            call_res = self.provider.start_session(
                interview_id=str(self.interview.id),
                candidate_phone=self.interview.candidate.phone_number or "+10000000000",
                duration_limit_seconds=self.interview.duration_limit_seconds,
                metadata={"recruiter_id": self.interview.created_by_id},
            )
        except VoiceProviderError as err:
            self.interview.transition_to(Interview.STATUS_FAILED, save=True)
            self._record_event(
                idempotency_key or f"start-fail-{timezone.now().timestamp()}",
                "session_start_failed",
                {"error": str(err)},
                status=InterviewEvent.STATUS_FAILED,
                error_message=str(err)
            )
            raise OrchestrationError(f"Voice provider failed to start session: {str(err)}", error_code="PROVIDER_START_FAILED")

        self.interview.provider_call_id = call_res.session_id
        self.interview.started_at = timezone.now()
        self.interview.validate_transition(Interview.STATUS_IN_PROGRESS)
        self.interview.status = Interview.STATUS_IN_PROGRESS
        self.interview.save(update_fields=['status', 'provider_call_id', 'started_at', 'updated_at'])

        # Step B: Record AI Introduction if present in plan_data and no transcripts exist yet
        intro_text = self.interview.plan_data.get('introduction')
        if intro_text and not self.interview.transcripts.exists():
            TranscriptEntry.objects.create(
                interview=self.interview,
                sequence_number=1,
                speaker=TranscriptEntry.SPEAKER_AI,
                text=intro_text,
                timestamp=timezone.now(),
            )

        self._record_event(
            idempotency_key or f"start-{self.interview.id}",
            "session_started",
            {"provider_call_id": call_res.session_id, "is_mock": call_res.is_mock},
            status=InterviewEvent.STATUS_PROCESSED
        )

        return self.get_session_state(message="Mock interview started successfully.")

    @transaction.atomic
    def advance_question(
        self,
        simulated_candidate_response: Optional[str] = None,
        simulate_silence: bool = False,
        simulate_disconnect: bool = False,
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Advances the interview:
        - If previous question awaits answer, accepts simulated candidate response.
        - Next, presents the next unanswered question.
        - If all questions answered or time limit reached, concludes interview.
        """
        if idempotency_key:
            existing_event = InterviewEvent.objects.filter(
                interview=self.interview,
                idempotency_key=idempotency_key
            ).first()
            if existing_event:
                return self.get_session_state(message="Question advance already processed (idempotent replay).")

        if self.interview.status != Interview.STATUS_IN_PROGRESS:
            raise OrchestrationError(
                f"Cannot advance interview in status '{self.interview.status}'. Interview must be in progress.",
                error_code="NOT_IN_PROGRESS"
            )

        # Time limit check
        timing = self._calculate_timing()
        if timing["is_expired"]:
            return self.conclude_interview(reason="Time limit expired.")

        # Disconnection handling
        if simulate_disconnect:
            return self.fail_interview(
                reason="Candidate disconnected during interview.",
                error_code="CANDIDATE_DISCONNECTED"
            )

        # Get latest transcript entry to determine current sequence and state
        last_entry = self.interview.transcripts.order_by('-sequence_number').first()
        next_seq = (last_entry.sequence_number + 1) if last_entry else 1

        # Check if the last speaker was AI asking a question (not just intro)
        # Sequence 1 with intro does not require candidate answer to proceed to Q1
        ai_question_entries = [
            t for t in self.interview.transcripts.all()
            if t.speaker == TranscriptEntry.SPEAKER_AI and t.text.startswith("Question ")
        ]

        if last_entry and last_entry.speaker == TranscriptEntry.SPEAKER_AI and ai_question_entries and last_entry.id == ai_question_entries[-1].id:
            # We must record candidate's response to this question before moving to next
            resp_res = self.provider.receive_candidate_response(
                session_id=self.interview.provider_call_id or "mock-session",
                simulated_text=simulated_candidate_response,
                simulate_silence=simulate_silence,
                simulate_disconnect=simulate_disconnect,
            )

            response_text = "[Candidate remained silent]" if resp_res.is_silence else resp_res.response_text
            TranscriptEntry.objects.create(
                interview=self.interview,
                sequence_number=next_seq,
                speaker=TranscriptEntry.SPEAKER_CANDIDATE,
                text=response_text,
                timestamp=timezone.now(),
            )
            next_seq += 1

        # Determine which question index to deliver next
        # Count how many AI question entries have been asked
        # Note: sequence 1 might be introduction
        ai_entries = self.interview.transcripts.filter(speaker=TranscriptEntry.SPEAKER_AI).count()
        intro_present = bool(self.interview.plan_data.get('introduction'))
        questions_asked_count = (ai_entries - 1) if intro_present else ai_entries
        questions_asked_count = max(0, questions_asked_count)

        questions = list(self.interview.questions.order_by('sequence_number'))
        if questions_asked_count < len(questions):
            next_question = questions[questions_asked_count]
            # Deliver question
            self.provider.deliver_question(
                session_id=self.interview.provider_call_id or "mock-session",
                sequence_number=next_question.sequence_number,
                question_text=next_question.question_text,
            )
            TranscriptEntry.objects.create(
                interview=self.interview,
                sequence_number=next_seq,
                speaker=TranscriptEntry.SPEAKER_AI,
                text=f"Question {next_question.sequence_number}: {next_question.question_text}",
                timestamp=timezone.now(),
            )
            self._record_event(
                idempotency_key or f"ask-q{next_question.sequence_number}-{timezone.now().timestamp()}",
                "question_delivered",
                {"question_id": next_question.id, "sequence": next_question.sequence_number},
                status=InterviewEvent.STATUS_PROCESSED
            )
            return self.get_session_state(message=f"Delivered Question {next_question.sequence_number}.")
        else:
            # All questions asked and answered
            return self.conclude_interview(reason="All planned interview questions answered.")

    @transaction.atomic
    def conclude_interview(self, reason: str = "Completed planned questions.") -> Dict[str, Any]:
        """Gracefully concludes an active in-progress interview."""
        if self.interview.status == Interview.STATUS_COMPLETED:
            return self.get_session_state(message="Interview was already completed.")

        if self.interview.status != Interview.STATUS_IN_PROGRESS:
            raise OrchestrationError(
                f"Cannot conclude interview from status '{self.interview.status}'.",
                error_code="INVALID_STATUS"
            )

        # Deliver closing statement if configured
        closing = self.interview.plan_data.get('closing_statement')
        if closing:
            last_entry = self.interview.transcripts.order_by('-sequence_number').first()
            next_seq = (last_entry.sequence_number + 1) if last_entry else 1
            TranscriptEntry.objects.create(
                interview=self.interview,
                sequence_number=next_seq,
                speaker=TranscriptEntry.SPEAKER_AI,
                text=closing,
                timestamp=timezone.now(),
            )

        self.interview.ended_at = timezone.now()
        self.interview.validate_transition(Interview.STATUS_COMPLETED)
        self.interview.status = Interview.STATUS_COMPLETED
        self.interview.save(update_fields=['status', 'ended_at', 'updated_at'])

        if self.interview.provider_call_id:
            self.provider.end_session(self.interview.provider_call_id, reason=reason)

        self._record_event(
            f"conclude-{self.interview.id}",
            "session_completed",
            {"reason": reason},
            status=InterviewEvent.STATUS_PROCESSED
        )

        return self.get_session_state(message=f"Interview completed: {reason}")

    @transaction.atomic
    def cancel_interview(self, reason: str = "Cancelled by recruiter.") -> Dict[str, Any]:
        """Cancels a draft, scheduled, calling, or in_progress interview."""
        if self.interview.status == Interview.STATUS_CANCELLED:
            return self.get_session_state(message="Interview was already cancelled.")

        self.interview.ended_at = timezone.now()
        self.interview.validate_transition(Interview.STATUS_CANCELLED)
        self.interview.status = Interview.STATUS_CANCELLED
        self.interview.save(update_fields=['status', 'ended_at', 'updated_at'])

        if self.interview.provider_call_id:
            self.provider.end_session(self.interview.provider_call_id, reason=reason)

        self._record_event(
            f"cancel-{self.interview.id}",
            "session_cancelled",
            {"reason": reason},
            status=InterviewEvent.STATUS_PROCESSED
        )

        return self.get_session_state(message=f"Interview cancelled: {reason}")

    @transaction.atomic
    def fail_interview(self, reason: str, error_code: str = "GENERAL_FAILURE") -> Dict[str, Any]:
        """Marks interview as failed and ends mock session."""
        if self.interview.status == Interview.STATUS_FAILED:
            return self.get_session_state(message="Interview was already marked as failed.")

        self.interview.transition_to(Interview.STATUS_FAILED, save=True)
        self.interview.ended_at = timezone.now()
        self.interview.save(update_fields=['ended_at'])

        if self.interview.provider_call_id:
            self.provider.end_session(self.interview.provider_call_id, reason=reason)

        self._record_event(
            f"fail-{self.interview.id}-{timezone.now().timestamp()}",
            "session_failed",
            {"reason": reason, "error_code": error_code},
            status=InterviewEvent.STATUS_FAILED,
            error_message=reason
        )

        return self.get_session_state(message=f"Interview failed: {reason}")

    def get_session_state(self, message: str = "") -> Dict[str, Any]:
        """Returns comprehensive session state for frontend and API responses."""
        timing = self._calculate_timing()
        questions = list(self.interview.questions.order_by('sequence_number'))
        transcripts = list(self.interview.transcripts.order_by('sequence_number'))

        # Determine current active question
        ai_entries = [t for t in transcripts if t.speaker == TranscriptEntry.SPEAKER_AI]
        intro_present = bool(self.interview.plan_data.get('introduction'))
        questions_asked = (len(ai_entries) - 1) if intro_present else len(ai_entries)
        questions_asked = max(0, questions_asked)

        current_q = None
        if 0 < questions_asked <= len(questions):
            current_q = questions[questions_asked - 1]
        elif questions_asked == 0 and questions:
            current_q = questions[0]

        last_entry = transcripts[-1] if transcripts else None
        awaiting_candidate_response = (
            self.interview.status == Interview.STATUS_IN_PROGRESS and
            last_entry is not None and
            last_entry.speaker == TranscriptEntry.SPEAKER_AI
        )

        return {
            "interview_id": str(self.interview.id),
            "status": self.interview.status,
            "provider_call_id": self.interview.provider_call_id,
            "is_mock": True,
            "simulation_disclaimer": "Simulated mock session only. No real phone call or live audio is transmitted.",
            "candidate": {
                "id": str(self.interview.candidate_id),
                "name": self.interview.candidate.full_name,
                "email": self.interview.candidate.email,
                "phone": self.interview.candidate.phone_number,
                "consent_status": self.interview.candidate.consent_status,
                "consent_recorded_at": self.interview.candidate.consent_recorded_at,
                "consent_method": self.interview.candidate.consent_method,
            },
            "job": {
                "id": str(self.interview.job_id),
                "title": self.interview.job.title,
            },
            "timing": timing,
            "current_question": {
                "id": current_q.id if current_q else None,
                "sequence_number": current_q.sequence_number if current_q else None,
                "text": current_q.question_text if current_q else None,
                "category": current_q.category if current_q else None,
                "competency": current_q.competency if current_q else None,
                "expected_evidence": current_q.expected_evidence if current_q else None,
                "suggested_follow_up": current_q.suggested_follow_up if current_q else None,
            } if current_q else None,
            "progress": {
                "total_questions": len(questions),
                "questions_asked": min(questions_asked, len(questions)),
                "is_completed": self.interview.status == Interview.STATUS_COMPLETED,
                "awaiting_candidate_response": awaiting_candidate_response,
            },
            "transcripts": [
                {
                    "id": t.id,
                    "sequence_number": t.sequence_number,
                    "speaker": t.speaker,
                    "text": t.text,
                    "timestamp": t.timestamp.isoformat(),
                }
                for t in transcripts
            ],
            "message": message,
        }

    def _record_event(
        self,
        idempotency_key: str,
        event_type: str,
        payload: Dict[str, Any],
        status: str = InterviewEvent.STATUS_PROCESSED,
        error_message: str = "",
    ):
        try:
            InterviewEvent.objects.create(
                interview=self.interview,
                idempotency_key=idempotency_key,
                event_type=event_type,
                payload=payload,
                processing_status=status,
                error_message=error_message,
            )
        except Exception as e:
            logger.warning("Failed to record InterviewEvent %s: %s", idempotency_key, e)

import logging
from typing import Optional, Dict, Any, Tuple
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from django.http import HttpResponse

from interviews.models import (
    Interview,
    InterviewQuestion,
    TranscriptEntry,
    CandidateInterviewAccessToken,
)
from candidates.models import Candidate
from interviews.services.orchestrator import (
    InterviewOrchestrationService,
    OrchestrationError,
    ConsentRequiredError,
    PlanRequiredError,
)
from integrations.speech.factory import SpeechProviderFactory
from integrations.speech.base import SpeechError, AudioValidationError

logger = logging.getLogger(__name__)


def get_token_from_request(request) -> Optional[str]:
    """
    Extracts candidate access token from Authorization header (Bearer <token>),
    X-Candidate-Token header, or ?token= query parameter.
    """
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        parts = auth_header.split(" ")
        if len(parts) == 2 and not parts[1].startswith("eyJ"):  # Avoid picking JWT
            return parts[1].strip()

    custom_header = request.headers.get("X-Candidate-Token")
    if custom_header:
        return custom_header.strip()

    query_token = request.query_params.get("token")
    if query_token:
        return query_token.strip()

    return None


def authenticate_candidate_token(request) -> Tuple[Optional[CandidateInterviewAccessToken], Optional[Response]]:
    """
    Validates the candidate access token and returns (token_obj, error_response).
    """
    raw_token = get_token_from_request(request)
    if not raw_token:
        return None, Response(
            {"detail": "Candidate access token is required.", "error_code": "TOKEN_REQUIRED"},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    token_hash = CandidateInterviewAccessToken.hash_token(raw_token)
    token_obj = CandidateInterviewAccessToken.objects.select_related(
        "interview", "interview__candidate", "interview__job"
    ).filter(token_hash=token_hash).first()

    if not token_obj:
        return None, Response(
            {"detail": "Invalid candidate access token.", "error_code": "INVALID_TOKEN"},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    if token_obj.is_revoked:
        return None, Response(
            {"detail": "This candidate interview link has been revoked.", "error_code": "TOKEN_REVOKED"},
            status=status.HTTP_403_FORBIDDEN,
        )

    if timezone.now() >= token_obj.expires_at:
        return None, Response(
            {"detail": "This candidate interview link has expired.", "error_code": "TOKEN_EXPIRED"},
            status=status.HTTP_403_FORBIDDEN,
        )

    interview = token_obj.interview
    if interview.status in [Interview.STATUS_COMPLETED, Interview.STATUS_CANCELLED]:
        return None, Response(
            {"detail": f"This interview has already concluded ({interview.status}).", "error_code": "INTERVIEW_CONCLUDED"},
            status=status.HTTP_410_GONE,
        )

    return token_obj, None


class CandidateBaseView(APIView):
    """
    Base view for candidate-facing endpoints.
    Disables global JWT authentication so candidate access tokens are not
    intercepted or rejected by SimpleJWT.
    """
    authentication_classes = []
    permission_classes = [permissions.AllowAny]


class CandidateSessionView(CandidateBaseView):

    def get(self, request):
        token_obj, error_resp = authenticate_candidate_token(request)
        if error_resp:
            return error_resp

        interview = token_obj.interview
        candidate = interview.candidate
        job = interview.job

        orchestrator = InterviewOrchestrationService(interview)
        timing = orchestrator._calculate_timing()

        # Gather public transcripts (only spoken texts, no recruiter evaluation notes)
        transcripts = [
            {
                "id": t.id,
                "sequence_number": t.sequence_number,
                "speaker": t.speaker,
                "text": t.text,
                "timestamp": t.timestamp.isoformat(),
            }
            for t in interview.transcripts.order_by("sequence_number")
        ]

        # Calculate progress
        total_questions = interview.questions.count()
        ai_entries = interview.transcripts.filter(
            speaker=TranscriptEntry.SPEAKER_AI,
            text__startswith="Question "
        ).count()

        return Response({
            "interview_id": str(interview.id),
            "status": interview.status,
            "candidate": {
                "name": candidate.full_name,
                "consent_status": candidate.consent_status,
                "consent_recorded_at": candidate.consent_recorded_at,
            },
            "job": {
                "title": job.title,
                "description": job.description,
            },
            "timing": timing,
            "progress": {
                "total_questions": total_questions,
                "questions_asked": min(ai_entries, total_questions),
                "is_completed": interview.status == Interview.STATUS_COMPLETED,
            },
            "transcripts": transcripts,
            "disclosure": {
                "ai_interviewer": True,
                "speech_recognition": True,
                "speech_synthesis": True,
                "audio_retention": "Temporary only during active turn transcription. Audio is immediately discarded and never stored permanently.",
                "duration_limit_minutes": int(interview.duration_limit_seconds / 60),
            }
        }, status=status.HTTP_200_OK)


class CandidateConsentView(CandidateBaseView):
    """
    POST /api/v1/candidate/consent/
    Records candidate's explicit consent before granting microphone or starting interview.
    """

    def post(self, request):
        token_obj, error_resp = authenticate_candidate_token(request)
        if error_resp:
            return error_resp

        consent_granted = request.data.get("consent_granted", False)
        consent_method = request.data.get("consent_method", "Candidate Web Portal Checkbox")

        if not consent_granted:
            return Response(
                {"detail": "Explicit consent is required to proceed with the AI interview.", "error_code": "CONSENT_REJECTED"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        candidate = token_obj.interview.candidate
        candidate.consent_status = Candidate.CONSENT_GRANTED
        candidate.consent_recorded_at = timezone.now()
        candidate.consent_method = consent_method
        candidate.save(update_fields=["consent_status", "consent_recorded_at", "consent_method"])

        return Response({
            "status": "granted",
            "consent_recorded_at": candidate.consent_recorded_at.isoformat(),
            "consent_method": candidate.consent_method,
            "message": "Candidate consent successfully recorded.",
        }, status=status.HTTP_200_OK)


class CandidateStartInterviewView(CandidateBaseView):
    """
    POST /api/v1/candidate/start/
    Initiates the interview: transitions to in_progress, delivers introduction,
    synthesizes first interviewer utterance.
    """

    def post(self, request):
        token_obj, error_resp = authenticate_candidate_token(request)
        if error_resp:
            return error_resp

        interview = token_obj.interview
        orchestrator = InterviewOrchestrationService(interview)

        try:
            state = orchestrator.start_interview()
        except ConsentRequiredError as err:
            return Response({"detail": str(err), "error_code": err.error_code}, status=status.HTTP_400_BAD_REQUEST)
        except PlanRequiredError as err:
            return Response({"detail": str(err), "error_code": err.error_code}, status=status.HTTP_400_BAD_REQUEST)
        except OrchestrationError as err:
            return Response({"detail": str(err), "error_code": err.error_code}, status=status.HTTP_400_BAD_REQUEST)

        # Mark token used timestamp
        if not token_obj.used_at:
            token_obj.used_at = timezone.now()
            token_obj.save(update_fields=["used_at"])

        # Fetch first interviewer message to synthesize
        first_ai_entry = interview.transcripts.filter(speaker=TranscriptEntry.SPEAKER_AI).order_by("sequence_number").first()
        interviewer_message = first_ai_entry.text if first_ai_entry else (interview.plan_data.get("introduction") or "Welcome to your interview.")

        return Response({
            "session_state": state,
            "current_message": interviewer_message,
            "message_id": first_ai_entry.id if first_ai_entry else None,
        }, status=status.HTTP_200_OK)


class CandidateSubmitTurnView(CandidateBaseView):
    """
    POST /api/v1/candidate/submit-turn/
    Candidate uploads spoken answer (WAV/WebM) -> STT transcribes -> Orchestrator advances
    -> Nemotron generates follow-up or next question -> TTS synthesizes speech audio.
    """

    def post(self, request):
        token_obj, error_resp = authenticate_candidate_token(request)
        if error_resp:
            return error_resp

        interview = token_obj.interview

        # Pre-condition: candidate consent must be granted
        if interview.candidate.consent_status != Candidate.CONSENT_GRANTED:
            return Response(
                {"detail": "Candidate consent has not been granted.", "error_code": "CONSENT_NOT_GRANTED"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if interview.status != Interview.STATUS_IN_PROGRESS:
            return Response(
                {"detail": f"Interview is not in progress (current status: {interview.status}).", "error_code": "NOT_IN_PROGRESS"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Extract audio payload
        audio_file = request.FILES.get("audio")
        simulated_text = request.data.get("simulated_text")  # For automated test fallback

        candidate_text = ""
        stt_provider = SpeechProviderFactory.get_stt_provider()

        if audio_file:
            content_type = audio_file.content_type or "audio/wav"
            audio_bytes = audio_file.read()

            try:
                stt_result = stt_provider.transcribe(
                    audio_bytes=audio_bytes,
                    content_type=content_type,
                    language="en-IN",
                    metadata={"interview_id": str(interview.id)},
                )
                candidate_text = stt_result.text
            except AudioValidationError as err:
                return Response({"detail": str(err), "error_code": err.error_code}, status=status.HTTP_400_BAD_REQUEST)
            except SpeechError as err:
                return Response({"detail": str(err), "error_code": err.error_code}, status=status.HTTP_502_BAD_GATEWAY)
        elif simulated_text:
            candidate_text = simulated_text.strip()
        else:
            return Response(
                {"detail": "No audio file or response text provided in request.", "error_code": "MISSING_AUDIO"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Step 2: Advance interview through Orchestrator (Nemotron dialogue + follow-up evaluation)
        orchestrator = InterviewOrchestrationService(interview)
        try:
            state = orchestrator.advance_question(
                simulated_candidate_response=candidate_text or "[Candidate spoke unintelligibly]",
            )
        except OrchestrationError as err:
            return Response({"detail": str(err), "error_code": err.error_code}, status=status.HTTP_400_BAD_REQUEST)

        # Step 3: Extract the latest interviewer message
        last_ai_entry = interview.transcripts.filter(speaker=TranscriptEntry.SPEAKER_AI).order_by("-sequence_number").first()
        interviewer_message = last_ai_entry.text if last_ai_entry else ""

        return Response({
            "candidate_transcript": candidate_text,
            "session_state": state,
            "interviewer_message": interviewer_message,
            "interviewer_message_id": last_ai_entry.id if last_ai_entry else None,
            "is_completed": interview.status == Interview.STATUS_COMPLETED,
        }, status=status.HTTP_200_OK)


class CandidateSynthesizeSpeechView(CandidateBaseView):
    """
    POST /api/v1/candidate/synthesize-speech/
    Synthesizes speech audio for an authorized candidate session.
    """

    def post(self, request):
        token_obj, error_resp = authenticate_candidate_token(request)
        if error_resp:
            return error_resp

        interview = token_obj.interview
        message = request.data.get("message")
        transcript_id = request.data.get("transcript_id")

        if not message and transcript_id:
            entry = interview.transcripts.filter(id=transcript_id, speaker=TranscriptEntry.SPEAKER_AI).first()
            if entry:
                message = entry.text

        if not message or not str(message).strip():
            return Response(
                {"detail": "No valid interviewer message provided for synthesis.", "error_code": "EMPTY_MESSAGE"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        tts_provider = SpeechProviderFactory.get_tts_provider()
        try:
            result = tts_provider.synthesize(
                text=str(message).strip(),
                language="en-IN",
                output_format="audio/wav",
                metadata={"interview_id": str(interview.id)},
            )
            resp = HttpResponse(result.audio_bytes, content_type=result.audio_format)
            resp["Content-Disposition"] = f'inline; filename="interview-{interview.id}-speech.{result.audio_format.split("/")[-1]}"'
            resp["X-Speech-Provider"] = result.provider_name
            resp["X-Speech-Duration"] = str(result.duration_seconds)
            return resp
        except AudioValidationError as err:
            return Response({"detail": str(err), "error_code": err.error_code}, status=status.HTTP_400_BAD_REQUEST)
        except SpeechError as err:
            return Response({"detail": str(err), "error_code": err.error_code}, status=status.HTTP_502_BAD_GATEWAY)

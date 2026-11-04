import logging
from django.db import transaction
from django.urls import reverse
from django.utils import timezone
from django.http import HttpResponse
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from accounts.permissions import IsRecruiterUser
from interviews.models import Interview, InterviewQuestion, TranscriptEntry
from interviews.serializers import (
    InterviewListSerializer,
    InterviewDetailSerializer,
    InterviewQuestionSerializer,
    TranscriptEntrySerializer,
)
from evaluations.models import EvaluationResult
from evaluations.serializers import EvaluationResultSerializer
from operations.models import AsyncOperation
from interviews.tasks import generate_plan_task
from interviews.services.question_generator import (
    generate_interview_plan,
    ConfigurationError,
    OpenAIServiceError,
    PlanValidationError,
    QuestionGenerationError,
)
from interviews.services.orchestrator import (
    InterviewOrchestrationService,
    OrchestrationError,
    ConsentRequiredError,
    PlanRequiredError,
    TimeLimitExceededError,
)
from interviews.models import InterviewStatusTransitionError
from integrations.speech.factory import SpeechProviderFactory
from integrations.speech.base import SpeechError, AudioValidationError

logger = logging.getLogger(__name__)


class InterviewViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated, IsRecruiterUser]

    def get_queryset(self):
        return Interview.objects.filter(
            created_by=self.request.user
        ).select_related('candidate', 'job')

    def get_serializer_class(self):
        if self.action == 'list':
            return InterviewListSerializer
        return InterviewDetailSerializer

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def destroy(self, request, *args, **kwargs):
        interview = self.get_object()
        # Safe deletion: prevent deleting if interview was ever initiated or has transcript/evaluation
        if interview.status in [Interview.STATUS_IN_PROGRESS, Interview.STATUS_COMPLETED] or \
           interview.transcripts.exists() or hasattr(interview, 'evaluation'):
            return Response(
                {"detail": "Cannot delete interview with recorded execution history or evaluations."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=['get'], url_path='questions')
    def questions(self, request, pk=None):
        interview = self.get_object()
        questions = interview.questions.all().order_by('sequence_number')
        serializer = InterviewQuestionSerializer(questions, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'], url_path='transcript')
    def transcript(self, request, pk=None):
        interview = self.get_object()
        transcripts = interview.transcripts.all().order_by('sequence_number')
        serializer = TranscriptEntrySerializer(transcripts, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'], url_path='evaluation')
    def evaluation(self, request, pk=None):
        interview = self.get_object()
        if not hasattr(interview, 'evaluation'):
            # Return 200 with status pending if interview is completed but task is queuing, or 404 if draft
            if interview.status == Interview.STATUS_COMPLETED:
                return Response({
                    "interview_id": str(interview.id),
                    "evaluation_status": "pending",
                    "evaluation": None,
                    "message": "Evaluation has been scheduled and is processing.",
                }, status=status.HTTP_200_OK)
            return Response(
                {"detail": "No evaluation found for this interview."},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = EvaluationResultSerializer(interview.evaluation)
        return Response(serializer.data)

    @action(detail=True, methods=['patch', 'post'], url_path='evaluation/review')
    def evaluation_review(self, request, pk=None):
        """
        Records the recruiter's human hiring decision ('hire', 'hold', 'reject')
        and evaluation review notes.
        """
        interview = self.get_object()
        if interview.status != Interview.STATUS_COMPLETED:
            return Response(
                {"detail": "Cannot review evaluation for an uncompleted interview.", "error_code": "INTERVIEW_NOT_COMPLETED"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not hasattr(interview, 'evaluation'):
            return Response(
                {"detail": "No evaluation found to review. Please generate or retry evaluation first.", "error_code": "EVALUATION_NOT_FOUND"},
                status=status.HTTP_404_NOT_FOUND,
            )

        eval_obj = interview.evaluation
        if eval_obj.evaluation_status in [EvaluationResult.EVAL_STATUS_PENDING, EvaluationResult.EVAL_STATUS_PROCESSING]:
            return Response(
                {"detail": "Evaluation is still processing. Please wait for completion before recording your review.", "error_code": "EVALUATION_PROCESSING"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        final_decision = request.data.get('final_decision')
        recruiter_notes = request.data.get('recruiter_notes', '')

        # Validation
        valid_decisions = [EvaluationResult.DECISION_HIRE, EvaluationResult.DECISION_HOLD, EvaluationResult.DECISION_REJECT]
        if final_decision not in valid_decisions:
            return Response(
                {"detail": f"Invalid final decision '{final_decision}'. Allowed values: {valid_decisions}.", "error_code": "INVALID_DECISION"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if len(str(recruiter_notes)) > 5000:
            return Response(
                {"detail": "Recruiter notes exceed the 5000 character limit.", "error_code": "NOTES_TOO_LONG"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from django.utils import timezone
        eval_obj.final_decision = final_decision
        eval_obj.recruiter_notes = str(recruiter_notes).strip()
        eval_obj.review_status = EvaluationResult.STATUS_REVIEWED
        eval_obj.reviewed_by = request.user
        eval_obj.reviewed_at = timezone.now()
        eval_obj.save(update_fields=['final_decision', 'recruiter_notes', 'review_status', 'reviewed_by', 'reviewed_at', 'updated_at'])

        serializer = EvaluationResultSerializer(eval_obj)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='evaluation/retry')
    def evaluation_retry(self, request, pk=None):
        """
        Manually retries or initiates evaluation generation for an eligible completed interview.
        """
        interview = self.get_object()
        if interview.status != Interview.STATUS_COMPLETED:
            return Response(
                {"detail": "Only completed interviews can be evaluated.", "error_code": "INTERVIEW_NOT_COMPLETED"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check if already reviewed
        if hasattr(interview, 'evaluation'):
            eval_obj = interview.evaluation
            if eval_obj.review_status == EvaluationResult.STATUS_REVIEWED:
                return Response(
                    {"detail": "This evaluation has already been reviewed by a recruiter and cannot be regenerated.", "error_code": "ALREADY_REVIEWED"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if eval_obj.evaluation_status == EvaluationResult.EVAL_STATUS_PROCESSING:
                return Response(
                    {"detail": "Evaluation is already being generated in the background.", "error_code": "ALREADY_PROCESSING"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if eval_obj.evaluation_status == EvaluationResult.EVAL_STATUS_COMPLETED:
                return Response(
                    {"detail": "Evaluation is already completed.", "error_code": "ALREADY_COMPLETED"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        from evaluations.tasks import generate_evaluation_task

        # Preserve the existing evaluation status and error message to safely rollback if broker dispatch fails
        previous_status = getattr(interview.evaluation, 'evaluation_status', None) if hasattr(interview, 'evaluation') else None
        previous_error = getattr(interview.evaluation, 'error_message', '') if hasattr(interview, 'evaluation') else ''

        # Transition or initialize evaluation record to processing
        eval_obj, _ = EvaluationResult.objects.update_or_create(
            interview=interview,
            defaults={"evaluation_status": EvaluationResult.EVAL_STATUS_PROCESSING, "error_message": ""}
        )

        try:
            generate_evaluation_task.delay(str(interview.id))
        except Exception as e:
            # Revert state safely using row-level locking to avoid race conditions with a worker
            with transaction.atomic():
                locked_eval = EvaluationResult.objects.select_for_update().filter(interview=interview).first()
                if locked_eval:
                    # Do not revert if already reviewed or completed
                    if locked_eval.review_status != EvaluationResult.STATUS_REVIEWED and \
                       locked_eval.evaluation_status != EvaluationResult.EVAL_STATUS_COMPLETED:
                        # Restore previous status if eligible or fallback to failed with sanitized broker error
                        fallback_status = previous_status if previous_status in [
                            EvaluationResult.EVAL_STATUS_FAILED,
                            EvaluationResult.EVAL_STATUS_INSUFFICIENT
                        ] else EvaluationResult.EVAL_STATUS_FAILED
                        locked_eval.evaluation_status = fallback_status
                        locked_eval.error_message = previous_error or "Task broker unavailable. Please retry."
                        locked_eval.save(update_fields=['evaluation_status', 'error_message', 'updated_at'])

            return Response(
                {"detail": "Task broker unavailable. Please try again later.", "error_code": "BROKER_UNAVAILABLE"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        return Response({
            "interview_id": str(interview.id),
            "evaluation_status": "processing",
            "message": "Evaluation generation task enqueued.",
        }, status=status.HTTP_202_ACCEPTED)

    @action(detail=True, methods=['post'], url_path='generate-plan')
    def generate_plan(self, request, pk=None):
        interview = self.get_object()

        # 1. Cross-recruiter checks
        if interview.candidate.created_by != request.user or interview.job.created_by != request.user:
            return Response(
                {"detail": "Associated candidate or job belongs to another recruiter."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # 2. Status check: only allowed while interview is in draft status
        if interview.status != Interview.STATUS_DRAFT:
            return Response(
                {"detail": f"Interview plan can only be generated for draft interviews. Current status: '{interview.status}'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 3. Check for existing questions
        if interview.questions.exists():
            return Response(
                {"detail": "An interview plan with questions already exists for this interview. Overwriting is not permitted."},
                status=status.HTTP_409_CONFLICT,
            )

        # Check for active running/pending plan generation to prevent duplicate tasks
        active_op = AsyncOperation.objects.filter(
            interview=interview,
            operation_type=AsyncOperation.TYPE_PLAN_GENERATION,
            status__in=[AsyncOperation.STATUS_PENDING, AsyncOperation.STATUS_RUNNING],
        ).first()
        if active_op:
            status_url = request.build_absolute_uri(
                reverse('operation-detail', kwargs={'pk': str(active_op.id)})
            )
            return Response(
                {
                    "detail": "A plan generation operation is already in progress for this interview.",
                    "operation_id": str(active_op.id),
                    "status": active_op.status,
                    "status_url": status_url,
                },
                status=status.HTTP_409_CONFLICT,
            )

        # 4. Resume text and Job requirements check
        resume_text = interview.candidate.extracted_resume_text
        if not resume_text or not resume_text.strip():
            return Response(
                {"detail": "Candidate resume text has not been extracted yet. Please extract resume text before generating plan."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        job_desc = interview.job.description
        if not job_desc or not job_desc.strip():
            return Response(
                {"detail": "Job description is empty. A valid job description is required to generate interview plan."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 5. Create AsyncOperation and dispatch Celery task on commit
        with transaction.atomic():
            operation = AsyncOperation.objects.create(
                operation_type=AsyncOperation.TYPE_PLAN_GENERATION,
                status=AsyncOperation.STATUS_PENDING,
                created_by=request.user,
                interview=interview,
                candidate=interview.candidate,
                status_message="Interview plan generation enqueued.",
            )

            def dispatch_task():
                try:
                    task = generate_plan_task.delay(
                        str(operation.id),
                        str(interview.id),
                    )
                    operation.celery_task_id = task.id
                    operation.save(update_fields=['celery_task_id'])
                except Exception as e:
                    operation.status = AsyncOperation.STATUS_FAILED
                    operation.status_message = "Task broker unavailable. Please try again shortly."
                    operation.error_code = "BROKER_UNAVAILABLE"
                    operation.save(update_fields=['status', 'status_message', 'error_code'])

            transaction.on_commit(dispatch_task)

        status_url = request.build_absolute_uri(
            reverse('operation-detail', kwargs={'pk': str(operation.id)})
        )

        return Response(
            {
                "status": "enqueued",
                "operation_id": str(operation.id),
                "operation_type": operation.operation_type,
                "interview_id": str(interview.id),
                "status_url": status_url,
                "message": "Interview plan generation request accepted.",
            },
            status=status.HTTP_202_ACCEPTED,
        )

    @action(detail=True, methods=['get'], url_path='session')
    def session(self, request, pk=None):
        interview = self.get_object()
        orchestrator = InterviewOrchestrationService(interview)
        state = orchestrator.get_session_state()
        return Response(state)

    @action(detail=True, methods=['post'], url_path='start')
    def start(self, request, pk=None):
        interview = self.get_object()
        idempotency_key = request.headers.get('Idempotency-Key') or request.data.get('idempotency_key')
        orchestrator = InterviewOrchestrationService(interview)
        try:
            state = orchestrator.start_interview(idempotency_key=idempotency_key)
            return Response(state, status=status.HTTP_200_OK)
        except ConsentRequiredError as err:
            return Response({"detail": str(err), "error_code": err.error_code}, status=status.HTTP_400_BAD_REQUEST)
        except PlanRequiredError as err:
            return Response({"detail": str(err), "error_code": err.error_code}, status=status.HTTP_400_BAD_REQUEST)
        except OrchestrationError as err:
            return Response({"detail": str(err), "error_code": err.error_code}, status=status.HTTP_400_BAD_REQUEST)
        except InterviewStatusTransitionError as err:
            return Response({"detail": str(err), "error_code": "INVALID_TRANSITION"}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], url_path='advance')
    def advance(self, request, pk=None):
        interview = self.get_object()
        idempotency_key = request.headers.get('Idempotency-Key') or request.data.get('idempotency_key')
        simulated_response = request.data.get('simulated_response')
        simulate_silence = bool(request.data.get('simulate_silence', False))
        simulate_disconnect = bool(request.data.get('simulate_disconnect', False))

        orchestrator = InterviewOrchestrationService(interview)
        try:
            state = orchestrator.advance_question(
                simulated_candidate_response=simulated_response,
                simulate_silence=simulate_silence,
                simulate_disconnect=simulate_disconnect,
                idempotency_key=idempotency_key,
            )
            return Response(state, status=status.HTTP_200_OK)
        except OrchestrationError as err:
            return Response({"detail": str(err), "error_code": err.error_code}, status=status.HTTP_400_BAD_REQUEST)
        except InterviewStatusTransitionError as err:
            return Response({"detail": str(err), "error_code": "INVALID_TRANSITION"}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], url_path='cancel')
    def cancel(self, request, pk=None):
        interview = self.get_object()
        reason = request.data.get('reason', 'Cancelled by recruiter.')
        orchestrator = InterviewOrchestrationService(interview)
        try:
            state = orchestrator.cancel_interview(reason=reason)
            return Response(state, status=status.HTTP_200_OK)
        except OrchestrationError as err:
            return Response({"detail": str(err), "error_code": err.error_code}, status=status.HTTP_400_BAD_REQUEST)
        except InterviewStatusTransitionError as err:
            return Response({"detail": str(err), "error_code": "INVALID_TRANSITION"}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], url_path='transcribe-audio')
    def transcribe_audio(self, request, pk=None):
        """
        Receives candidate audio upload, verifies consent & recruiter ownership,
        runs STT, and returns transcription result.
        """
        interview = self.get_object()

        # Verify candidate consent
        if interview.candidate.consent_status != interview.candidate.CONSENT_GRANTED:
            return Response(
                {"detail": "Candidate has not granted consent for audio processing.", "error_code": "CONSENT_NOT_GRANTED"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        audio_file = request.FILES.get('audio')
        if not audio_file:
            return Response(
                {"detail": "No audio file provided in request (expected 'audio' field).", "error_code": "MISSING_AUDIO"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        content_type = audio_file.content_type or 'audio/wav'
        audio_bytes = audio_file.read()

        stt_provider = SpeechProviderFactory.get_stt_provider()
        try:
            result = stt_provider.transcribe(
                audio_bytes=audio_bytes,
                content_type=content_type,
                language="en-IN",
                metadata={"interview_id": str(interview.id)},
            )
            return Response({
                "interview_id": str(interview.id),
                "text": result.text,
                "confidence": result.confidence,
                "duration_seconds": result.duration_seconds,
                "is_empty": result.is_empty,
                "provider": result.provider_name,
            }, status=status.HTTP_200_OK)
        except AudioValidationError as err:
            return Response({"detail": str(err), "error_code": err.error_code}, status=status.HTTP_400_BAD_REQUEST)
        except SpeechError as err:
            return Response({"detail": str(err), "error_code": err.error_code}, status=status.HTTP_502_BAD_GATEWAY)

    @action(detail=True, methods=['post'], url_path='synthesize-speech')
    def synthesize_speech(self, request, pk=None):
        """
        Synthesizes interviewer utterance into spoken audio.
        Guarantees that only approved candidate-facing messages are synthesized.
        """
        interview = self.get_object()

        # Consent check
        if interview.candidate.consent_status != interview.candidate.CONSENT_GRANTED:
            return Response(
                {"detail": "Candidate has not granted consent for audio processing.", "error_code": "CONSENT_NOT_GRANTED"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Message text extraction
        message = request.data.get('message')
        transcript_id = request.data.get('transcript_id')

        if not message and transcript_id:
            entry = interview.transcripts.filter(id=transcript_id, speaker=TranscriptEntry.SPEAKER_AI).first()
            if entry:
                message = entry.text
            else:
                return Response(
                    {"detail": "Specified transcript entry not found or not spoken by AI.", "error_code": "INVALID_TRANSCRIPT_ID"},
                    status=status.HTTP_404_NOT_FOUND,
                )

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
            resp['Content-Disposition'] = f'inline; filename="interview-{interview.id}-speech.{result.audio_format.split("/")[-1]}"'
            resp['X-Speech-Provider'] = result.provider_name
            resp['X-Speech-Duration'] = str(result.duration_seconds)
            return resp
        except AudioValidationError as err:
            return Response({"detail": str(err), "error_code": err.error_code}, status=status.HTTP_400_BAD_REQUEST)
        except SpeechError as err:
            return Response({"detail": str(err), "error_code": err.error_code}, status=status.HTTP_502_BAD_GATEWAY)


    @action(detail=True, methods=['post'], url_path='generate-candidate-link')
    def generate_candidate_link(self, request, pk=None):
        """
        Recruiter generates a secure, expiring, unguessable candidate interview link.
        Automatically queues an invitation email to candidate's registered email address.
        """
        interview = self.get_object()

        # Reject link generation for completed or cancelled interviews
        if interview.status in [Interview.STATUS_COMPLETED, Interview.STATUS_CANCELLED]:
            return Response(
                {"detail": f"Cannot generate interview link for interview with status '{interview.status}'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        valid_hours = int(request.data.get('valid_hours', 72))

        from interviews.models import CandidateInterviewAccessToken
        from interviews.tasks import send_candidate_invitation_email_task

        token_obj, raw_token = CandidateInterviewAccessToken.create_token(
            interview=interview,
            valid_hours=valid_hours,
        )

        recipient_email = getattr(interview.candidate, 'email', '') or ''
        token_obj.recipient_email = recipient_email
        token_obj.save(update_fields=['recipient_email'])

        # Construct candidate link URL
        frontend_url = request.build_absolute_uri(f"/interview/session?token={raw_token}")

        from interviews.services.token_crypto import encrypt_url
        token_obj.encrypted_candidate_url = encrypt_url(frontend_url)
        token_obj.save(update_fields=['encrypted_candidate_url'])

        # Queue invitation email asynchronously
        email_enqueued = False
        if recipient_email:
            try:
                send_candidate_invitation_email_task.delay(token_obj.id, frontend_url)
                email_enqueued = True
            except Exception as e:
                logger.error("Failed to enqueue candidate invitation email for interview %s: %s", interview.id, str(e))
        else:
            token_obj.delivery_status = CandidateInterviewAccessToken.DELIVERY_FAILED
            token_obj.delivery_error = "Candidate record has no registered email address."
            token_obj.save(update_fields=['delivery_status', 'delivery_error'])

        return Response({
            "interview_id": str(interview.id),
            "candidate_name": interview.candidate.full_name,
            "candidate_email": recipient_email,
            "raw_token": raw_token,
            "candidate_url": frontend_url,
            "expires_at": token_obj.expires_at.isoformat(),
            "email_delivery_status": token_obj.delivery_status,
            "email_enqueued": email_enqueued,
        }, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='resend-candidate-link')
    def resend_candidate_link(self, request, pk=None):
        """
        Recruiters can resend the interview invitation email for the existing active token
        without generating a replacement token or invalidating existing candidate links.
        """
        interview = self.get_object()

        if interview.status in [Interview.STATUS_COMPLETED, Interview.STATUS_CANCELLED]:
            return Response(
                {"detail": f"Cannot resend interview link for interview with status '{interview.status}'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        recipient_email = getattr(interview.candidate, 'email', '') or ''
        if not recipient_email:
            return Response(
                {"detail": "Candidate has no registered email address to receive invitations."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from interviews.models import CandidateInterviewAccessToken
        from interviews.tasks import send_candidate_invitation_email_task
        from interviews.services.token_crypto import decrypt_url

        # Fetch latest active token
        latest_token = CandidateInterviewAccessToken.objects.filter(interview=interview).order_by('-created_at').first()

        if not latest_token:
            return Response(
                {"detail": "No candidate interview link exists. Please generate a link first."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if latest_token.is_revoked:
            return Response(
                {"detail": "The existing candidate interview link has been revoked. Generate a replacement link instead."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if timezone.now() >= latest_token.expires_at:
            return Response(
                {"detail": "The existing candidate interview link has expired. Generate a replacement link instead."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Recover candidate URL from authenticated encrypted storage
        candidate_url = decrypt_url(latest_token.encrypted_candidate_url)
        if not candidate_url:
            return Response(
                {"detail": "Unable to recover link URL for resend. Please generate a replacement link."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Reset delivery status to pending for resend
        latest_token.delivery_status = CandidateInterviewAccessToken.DELIVERY_PENDING
        latest_token.delivery_error = ""
        latest_token.recipient_email = recipient_email
        latest_token.save(update_fields=['delivery_status', 'delivery_error', 'recipient_email'])

        try:
            send_candidate_invitation_email_task.delay(latest_token.id, candidate_url)
        except Exception as e:
            logger.error("Failed to enqueue candidate invitation email for interview %s: %s", interview.id, str(e))

        return Response({
            "interview_id": str(interview.id),
            "candidate_name": interview.candidate.full_name,
            "candidate_email": recipient_email,
            "candidate_url": candidate_url,
            "expires_at": latest_token.expires_at.isoformat(),
            "email_delivery_status": latest_token.delivery_status,
            "message": "Candidate interview invitation email enqueued for existing active link.",
        }, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='replace-candidate-link')
    def replace_candidate_link(self, request, pk=None):
        """
        Explicit recruiter action to revoke prior links, create a fresh replacement token,
        and dispatch a new invitation email.
        """
        interview = self.get_object()

        if interview.status in [Interview.STATUS_COMPLETED, Interview.STATUS_CANCELLED]:
            return Response(
                {"detail": f"Cannot replace interview link for interview with status '{interview.status}'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        recipient_email = getattr(interview.candidate, 'email', '') or ''
        if not recipient_email:
            return Response(
                {"detail": "Candidate has no registered email address to receive invitations."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        valid_hours = int(request.data.get('valid_hours', 72))
        from interviews.models import CandidateInterviewAccessToken
        from interviews.tasks import send_candidate_invitation_email_task
        from interviews.services.token_crypto import encrypt_url

        # Revoke all previous tokens explicitly
        CandidateInterviewAccessToken.objects.filter(
            interview=interview,
            is_revoked=False,
        ).update(is_revoked=True)

        token_obj, raw_token = CandidateInterviewAccessToken.create_token(
            interview=interview,
            valid_hours=valid_hours,
        )
        token_obj.recipient_email = recipient_email

        frontend_url = request.build_absolute_uri(f"/interview/session?token={raw_token}")
        token_obj.encrypted_candidate_url = encrypt_url(frontend_url)
        token_obj.save(update_fields=['recipient_email', 'encrypted_candidate_url'])

        try:
            send_candidate_invitation_email_task.delay(token_obj.id, frontend_url)
        except Exception as e:
            logger.error("Failed to enqueue candidate invitation email for interview %s: %s", interview.id, str(e))

        return Response({
            "interview_id": str(interview.id),
            "candidate_name": interview.candidate.full_name,
            "candidate_email": recipient_email,
            "raw_token": raw_token,
            "candidate_url": frontend_url,
            "expires_at": token_obj.expires_at.isoformat(),
            "email_delivery_status": token_obj.delivery_status,
            "message": "Previous links revoked. New replacement interview link generated and emailed.",
        }, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get'], url_path='candidate-link-status')
    def candidate_link_status(self, request, pk=None):
        """
        Retrieves current candidate link & email invitation status for recruiter dashboard.
        """
        interview = self.get_object()
        from interviews.models import CandidateInterviewAccessToken

        latest_token = CandidateInterviewAccessToken.objects.filter(interview=interview).order_by('-created_at').first()
        if not latest_token:
            return Response({
                "interview_id": str(interview.id),
                "has_token": False,
                "candidate_email": getattr(interview.candidate, 'email', '') or '',
            }, status=status.HTTP_200_OK)

        return Response({
            "interview_id": str(interview.id),
            "has_token": True,
            "is_valid": latest_token.is_valid,
            "is_revoked": latest_token.is_revoked,
            "is_expired": timezone.now() >= latest_token.expires_at,
            "created_at": latest_token.created_at.isoformat(),
            "expires_at": latest_token.expires_at.isoformat(),
            "used_at": latest_token.used_at.isoformat() if latest_token.used_at else None,
            "recipient_email": latest_token.recipient_email or getattr(interview.candidate, 'email', '') or '',
            "delivery_status": latest_token.delivery_status,
            "sent_at": latest_token.sent_at.isoformat() if latest_token.sent_at else None,
            "delivery_error": latest_token.delivery_error,
        }, status=status.HTTP_200_OK)

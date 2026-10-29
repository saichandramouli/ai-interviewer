from django.db import transaction
from django.urls import reverse
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from interviews.models import Interview, InterviewQuestion, TranscriptEntry
from interviews.serializers import (
    InterviewListSerializer,
    InterviewDetailSerializer,
    InterviewQuestionSerializer,
    TranscriptEntrySerializer,
)
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


class InterviewViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]

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
            return Response(
                {"detail": "No evaluation found for this interview."},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = EvaluationResultSerializer(interview.evaluation)
        return Response(serializer.data)

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


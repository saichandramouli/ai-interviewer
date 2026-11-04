from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from accounts.permissions import IsRecruiterUser
from candidates.models import Candidate
from candidates.serializers import CandidateListSerializer, CandidateDetailSerializer
from candidates.services.resume_extractor import (
    ResumeExtractorService,
    UnsupportedFileError,
    FileSizeLimitExceededError,
    CorruptedFileError,
    EncryptedFileError,
    EmptyDocumentError,
)


from django.db import transaction
from django.urls import reverse
from operations.models import AsyncOperation
from candidates.tasks import extract_resume_task


class CandidateViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated, IsRecruiterUser]

    def get_queryset(self):
        return Candidate.objects.filter(created_by=self.request.user)

    def get_serializer_class(self):
        if self.action == 'list':
            return CandidateListSerializer
        return CandidateDetailSerializer

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def destroy(self, request, *args, **kwargs):
        candidate = self.get_object()
        if candidate.interviews.exists():
            return Response(
                {"detail": "Cannot delete candidate with existing interview history. Archive instead."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=['post'], url_path='extract-resume')
    def extract_resume(self, request, pk=None):
        candidate = self.get_object()

        if not candidate.resume:
            return Response(
                {"detail": "No resume file has been uploaded for this candidate."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check for active running/pending extraction for this candidate to avoid duplicates
        active_op = AsyncOperation.objects.filter(
            candidate=candidate,
            operation_type=AsyncOperation.TYPE_RESUME_EXTRACTION,
            status__in=[AsyncOperation.STATUS_PENDING, AsyncOperation.STATUS_RUNNING],
        ).first()
        if active_op:
            status_url = request.build_absolute_uri(
                reverse('operation-detail', kwargs={'pk': str(active_op.id)})
            )
            return Response(
                {
                    "detail": "An extraction operation is already in progress for this candidate.",
                    "operation_id": str(active_op.id),
                    "status": active_op.status,
                    "status_url": status_url,
                },
                status=status.HTTP_409_CONFLICT,
            )

        fingerprint = f"{candidate.resume.name}:{getattr(candidate.resume, 'size', 0)}"

        with transaction.atomic():
            operation = AsyncOperation.objects.create(
                operation_type=AsyncOperation.TYPE_RESUME_EXTRACTION,
                status=AsyncOperation.STATUS_PENDING,
                created_by=request.user,
                candidate=candidate,
                target_fingerprint=fingerprint,
                status_message="Resume extraction enqueued.",
            )

            # Dispatch task safely on transaction commit
            def dispatch_task():
                try:
                    task = extract_resume_task.delay(
                        str(operation.id),
                        str(candidate.id),
                        fingerprint,
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
                "status_url": status_url,
                "message": "Resume extraction request accepted.",
            },
            status=status.HTTP_202_ACCEPTED,
        )

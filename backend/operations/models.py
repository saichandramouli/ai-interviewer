import uuid
from django.db import models
from django.conf import settings
from candidates.models import Candidate
from interviews.models import Interview


class AsyncOperation(models.Model):
    TYPE_RESUME_EXTRACTION = 'resume_extraction'
    TYPE_PLAN_GENERATION = 'plan_generation'
    TYPE_CHOICES = [
        (TYPE_RESUME_EXTRACTION, 'Resume Extraction'),
        (TYPE_PLAN_GENERATION, 'Plan Generation'),
    ]

    STATUS_PENDING = 'pending'
    STATUS_RUNNING = 'running'
    STATUS_SUCCEEDED = 'succeeded'
    STATUS_FAILED = 'failed'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_RUNNING, 'Running'),
        (STATUS_SUCCEEDED, 'Succeeded'),
        (STATUS_FAILED, 'Failed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    operation_type = models.CharField(max_length=50, choices=TYPE_CHOICES, db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING, db_index=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='operations',
    )
    candidate = models.ForeignKey(
        Candidate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='operations',
    )
    interview = models.ForeignKey(
        Interview,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='operations',
    )

    celery_task_id = models.CharField(max_length=255, blank=True, default='', db_index=True)
    status_message = models.CharField(max_length=255, blank=True, default='Operation enqueued.')
    error_code = models.CharField(max_length=100, blank=True, default='')
    attempt_count = models.PositiveIntegerField(default=0)

    # Fingerprint to guard against stale tasks if the candidate resume changed before worker ran
    target_fingerprint = models.CharField(max_length=255, blank=True, default='')

    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['created_by', 'status']),
            models.Index(fields=['operation_type', 'status']),
        ]

    def __str__(self):
        return f"{self.operation_type} [{self.status}] ({self.id})"

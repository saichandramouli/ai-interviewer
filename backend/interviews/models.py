import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.exceptions import ValidationError
from candidates.models import Candidate
from jobs.models import Job


class InterviewStatusTransitionError(ValidationError):
    """Raised when an invalid interview status transition is attempted."""
    pass


class Interview(models.Model):
    STATUS_DRAFT = 'draft'
    STATUS_SCHEDULED = 'scheduled'
    STATUS_CALLING = 'calling'
    STATUS_IN_PROGRESS = 'in_progress'
    STATUS_COMPLETED = 'completed'
    STATUS_FAILED = 'failed'
    STATUS_CANCELLED = 'cancelled'

    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Draft'),
        (STATUS_SCHEDULED, 'Scheduled'),
        (STATUS_CALLING, 'Calling'),
        (STATUS_IN_PROGRESS, 'In Progress'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_FAILED, 'Failed'),
        (STATUS_CANCELLED, 'Cancelled'),
    ]

    ALLOWED_TRANSITIONS = {
        STATUS_DRAFT: {STATUS_SCHEDULED, STATUS_CALLING, STATUS_CANCELLED},
        STATUS_SCHEDULED: {STATUS_CALLING, STATUS_CANCELLED},
        STATUS_CALLING: {STATUS_IN_PROGRESS, STATUS_FAILED, STATUS_CANCELLED},
        STATUS_IN_PROGRESS: {STATUS_COMPLETED, STATUS_FAILED, STATUS_CANCELLED},
        STATUS_COMPLETED: set(),
        STATUS_FAILED: {STATUS_DRAFT, STATUS_SCHEDULED},  # Allow reschedule/retry
        STATUS_CANCELLED: set(),
    }

    INITIATION_MANUAL = 'manual'
    INITIATION_SCHEDULED = 'scheduled'
    INITIATION_CHOICES = [
        (INITIATION_MANUAL, 'Manual'),
        (INITIATION_SCHEDULED, 'Scheduled'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    candidate = models.ForeignKey(
        Candidate,
        on_delete=models.PROTECT,
        related_name='interviews',
    )
    job = models.ForeignKey(
        Job,
        on_delete=models.PROTECT,
        related_name='interviews',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='interviews',
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_DRAFT,
        db_index=True,
    )
    initiation_type = models.CharField(
        max_length=20,
        choices=INITIATION_CHOICES,
        default=INITIATION_MANUAL,
    )
    scheduled_at = models.DateTimeField(null=True, blank=True)
    timezone = models.CharField(max_length=50, blank=True, default='UTC')
    duration_limit_seconds = models.PositiveIntegerField(default=1800)

    started_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)

    provider_call_id = models.CharField(
        max_length=255,
        unique=True,
        null=True,
        blank=True,
    )

    # Structured plan data (introduction, closing statement, plan metadata)
    plan_data = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['created_by', 'status']),
            models.Index(fields=['candidate', 'status']),
        ]

    def __str__(self):
        return f"Interview {self.id} - {self.candidate.full_name} ({self.status})"

    def validate_transition(self, new_status):
        if self.status == new_status:
            return
        allowed = self.ALLOWED_TRANSITIONS.get(self.status, set())
        if new_status not in allowed:
            raise InterviewStatusTransitionError(
                f"Cannot transition interview status from '{self.status}' to '{new_status}'."
            )

    def transition_to(self, new_status, save=True):
        self.validate_transition(new_status)
        self.status = new_status
        if save:
            self.save(update_fields=['status', 'updated_at'])


class InterviewQuestion(models.Model):
    id = models.BigAutoField(primary_key=True)
    interview = models.ForeignKey(
        Interview,
        on_delete=models.CASCADE,
        related_name='questions',
    )
    sequence_number = models.PositiveIntegerField()
    question_text = models.TextField()
    category = models.CharField(max_length=100, blank=True, default='general')
    competency = models.CharField(max_length=150, blank=True, default='')
    expected_evidence = models.TextField(blank=True, default='')
    suggested_follow_up = models.TextField(blank=True, default='')
    estimated_minutes = models.PositiveIntegerField(default=3)
    max_score = models.FloatField(default=10.0)

    class Meta:
        ordering = ['sequence_number']
        constraints = [
            models.UniqueConstraint(
                fields=['interview', 'sequence_number'],
                name='unique_interview_question_sequence',
            ),
        ]

    def __str__(self):
        return f"Q{self.sequence_number} for Interview {self.interview_id}"


class TranscriptEntry(models.Model):
    SPEAKER_AI = 'ai'
    SPEAKER_CANDIDATE = 'candidate'
    SPEAKER_SYSTEM = 'system'
    SPEAKER_CHOICES = [
        (SPEAKER_AI, 'AI'),
        (SPEAKER_CANDIDATE, 'Candidate'),
        (SPEAKER_SYSTEM, 'System'),
    ]

    id = models.BigAutoField(primary_key=True)
    interview = models.ForeignKey(
        Interview,
        on_delete=models.CASCADE,
        related_name='transcripts',
    )
    sequence_number = models.PositiveIntegerField()
    speaker = models.CharField(max_length=20, choices=SPEAKER_CHOICES)
    text = models.TextField()
    timestamp = models.DateTimeField()

    class Meta:
        ordering = ['sequence_number']
        constraints = [
            models.UniqueConstraint(
                fields=['interview', 'sequence_number'],
                name='unique_interview_transcript_sequence',
            ),
        ]

    def __str__(self):
        return f"[{self.speaker}] Q{self.sequence_number} ({self.interview_id})"


class InterviewEvent(models.Model):
    """
    Idempotent event log for provider, session, and interview lifecycle transitions.
    Prevents duplicate webhook / event processing.
    """
    STATUS_PENDING = 'pending'
    STATUS_PROCESSED = 'processed'
    STATUS_FAILED = 'failed'
    STATUS_IGNORED = 'ignored'

    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_PROCESSED, 'Processed'),
        (STATUS_FAILED, 'Failed'),
        (STATUS_IGNORED, 'Ignored'),
    ]

    id = models.BigAutoField(primary_key=True)
    interview = models.ForeignKey(
        Interview,
        on_delete=models.CASCADE,
        related_name='events',
    )
    idempotency_key = models.CharField(
        max_length=255,
        unique=True,
        db_index=True,
    )
    event_type = models.CharField(max_length=100)
    payload = models.JSONField(default=dict, blank=True)
    processing_status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
    )
    error_message = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['interview', 'event_type']),
        ]

    def __str__(self):
        return f"Event {self.event_type} ({self.idempotency_key}) - {self.processing_status}"



class CandidateInterviewAccessToken(models.Model):
    """
    Cryptographically secure, unguessable candidate interview access token.
    Stores only the SHA-256 hash. The raw token is never persisted.
    """
    id = models.BigAutoField(primary_key=True)
    interview = models.ForeignKey(
        Interview,
        on_delete=models.CASCADE,
        related_name='access_tokens',
    )
    token_hash = models.CharField(max_length=64, unique=True, db_index=True)
    created_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    is_revoked = models.BooleanField(default=False)

    # Email invitation delivery tracking
    DELIVERY_PENDING = 'pending'
    DELIVERY_SENDING = 'sending'
    DELIVERY_SENT = 'sent'
    DELIVERY_FAILED = 'failed'

    DELIVERY_CHOICES = [
        (DELIVERY_PENDING, 'Pending'),
        (DELIVERY_SENDING, 'Sending'),
        (DELIVERY_SENT, 'Sent'),
        (DELIVERY_FAILED, 'Failed'),
    ]

    delivery_status = models.CharField(
        max_length=20,
        choices=DELIVERY_CHOICES,
        default=DELIVERY_PENDING,
        db_index=True,
    )
    sent_at = models.DateTimeField(null=True, blank=True)
    delivery_started_at = models.DateTimeField(null=True, blank=True)
    recipient_email = models.EmailField(blank=True, default='')
    delivery_error = models.TextField(blank=True, default='')
    encrypted_candidate_url = models.TextField(blank=True, default='')

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['token_hash', 'is_revoked']),
        ]

    def __str__(self):
        return f"AccessToken for Interview {self.interview_id} (Revoked: {self.is_revoked})"

    @staticmethod
    def hash_token(raw_token: str) -> str:
        """Computes SHA-256 digest of raw candidate access token."""
        import hashlib
        return hashlib.sha256(raw_token.strip().encode('utf-8')).hexdigest()

    @classmethod
    def create_token(cls, interview: Interview, valid_hours: int = 72):
        """
        Generates a cryptographically secure random token, hashes it,
        and returns (token_instance, raw_token).
        """
        import secrets
        from datetime import timedelta
        raw_token = secrets.token_urlsafe(32)
        token_hash = cls.hash_token(raw_token)
        expires_at = timezone.now() + timedelta(hours=valid_hours)

        instance = cls.objects.create(
            interview=interview,
            token_hash=token_hash,
            expires_at=expires_at,
        )
        return instance, raw_token

    @property
    def is_valid(self) -> bool:
        """True if token is not revoked, not expired, and interview is not completed/cancelled."""
        if self.is_revoked:
            return False
        if timezone.now() >= self.expires_at:
            return False
        if self.interview.status in [Interview.STATUS_COMPLETED, Interview.STATUS_CANCELLED]:
            return False
        return True

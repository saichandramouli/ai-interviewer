import uuid
from django.db import models
from django.core.exceptions import ValidationError
from interviews.models import Interview


class EvaluationResult(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_REVIEWED = 'reviewed'

    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending Review'),
        (STATUS_REVIEWED, 'Reviewed'),
    ]

    EVAL_STATUS_PENDING = 'pending'
    EVAL_STATUS_PROCESSING = 'processing'
    EVAL_STATUS_COMPLETED = 'completed'
    EVAL_STATUS_FAILED = 'failed'
    EVAL_STATUS_INSUFFICIENT = 'insufficient_data'

    EVAL_STATUS_CHOICES = [
        (EVAL_STATUS_PENDING, 'Pending'),
        (EVAL_STATUS_PROCESSING, 'Processing'),
        (EVAL_STATUS_COMPLETED, 'Completed'),
        (EVAL_STATUS_FAILED, 'Failed'),
        (EVAL_STATUS_INSUFFICIENT, 'Insufficient Data'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    interview = models.OneToOneField(
        Interview,
        on_delete=models.CASCADE,
        related_name='evaluation',
    )
    overall_score = models.FloatField(null=True, blank=True)
    competency_scores = models.JSONField(default=dict, blank=True)
    strengths = models.JSONField(default=list, blank=True)
    improvement_areas = models.JSONField(default=list, blank=True)
    evidence_summary = models.TextField(blank=True, default='')

    review_status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        db_index=True,
    )
    evaluation_status = models.CharField(
        max_length=30,
        choices=EVAL_STATUS_CHOICES,
        default=EVAL_STATUS_PENDING,
        db_index=True,
    )
    error_message = models.TextField(blank=True, default='')

    # Recruiter human review fields
    DECISION_HIRE = 'hire'
    DECISION_HOLD = 'hold'
    DECISION_REJECT = 'reject'

    DECISION_CHOICES = [
        (DECISION_HIRE, 'Hire'),
        (DECISION_HOLD, 'Hold'),
        (DECISION_REJECT, 'Reject'),
    ]

    recruiter_notes = models.TextField(blank=True, default='')
    final_decision = models.CharField(
        max_length=20,
        choices=DECISION_CHOICES,
        null=True,
        blank=True,
        db_index=True,
    )
    reviewed_by = models.ForeignKey(
        'accounts.User',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='reviewed_evaluations',
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def clean(self):
        super().clean()
        if self.overall_score is not None:
            if not (0.0 <= self.overall_score <= 100.0):
                raise ValidationError({'overall_score': 'Overall score must be between 0 and 100.'})
        if not isinstance(self.competency_scores, dict):
            raise ValidationError({'competency_scores': 'Must be a dictionary of competency scores.'})
        if not isinstance(self.strengths, list):
            raise ValidationError({'strengths': 'Must be a list of strings.'})
        if not isinstance(self.improvement_areas, list):
            raise ValidationError({'improvement_areas': 'Must be a list of strings.'})

    def __str__(self):
        return f"Evaluation for Interview {self.interview_id} ({self.review_status})"

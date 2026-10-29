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

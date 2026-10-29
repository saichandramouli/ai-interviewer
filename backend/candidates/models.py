import os
import uuid
from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError


def validate_resume_file(value):
    ext = os.path.splitext(value.name)[1].lower()
    valid_extensions = ['.pdf', '.docx']
    if ext not in valid_extensions:
        raise ValidationError('Unsupported file extension. Allowed formats are: .pdf, .docx')
    max_size_mb = 10
    if value.size > max_size_mb * 1024 * 1024:
        raise ValidationError(f'File size exceeds the {max_size_mb}MB limit.')


def candidate_resume_upload_path(instance, filename):
    ext = os.path.splitext(filename)[1].lower()
    return f'resumes/{instance.created_by_id}/{instance.id}{ext}'


class Candidate(models.Model):
    CONSENT_PENDING = 'pending'
    CONSENT_GRANTED = 'granted'
    CONSENT_WITHDRAWN = 'withdrawn'

    CONSENT_CHOICES = [
        (CONSENT_PENDING, 'Pending'),
        (CONSENT_GRANTED, 'Granted'),
        (CONSENT_WITHDRAWN, 'Withdrawn'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    full_name = models.CharField(max_length=255)
    email = models.EmailField()
    phone_number = models.CharField(max_length=32, blank=True, default='')

    resume = models.FileField(
        upload_to=candidate_resume_upload_path,
        validators=[validate_resume_file],
        blank=True,
        null=True,
    )
    extracted_resume_text = models.TextField(blank=True, default='')

    consent_status = models.CharField(
        max_length=20,
        choices=CONSENT_CHOICES,
        default=CONSENT_PENDING,
        db_index=True,
    )
    consent_recorded_at = models.DateTimeField(null=True, blank=True)
    consent_method = models.CharField(max_length=100, blank=True, default='')

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='candidates',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['created_by', 'email']),
            models.Index(fields=['created_by', 'consent_status']),
        ]

    def __str__(self):
        return f"{self.full_name} ({self.email})"

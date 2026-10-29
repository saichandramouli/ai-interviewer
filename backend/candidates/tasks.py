import logging
from celery import shared_task
from django.utils import timezone
from operations.models import AsyncOperation
from candidates.models import Candidate
from candidates.services.resume_extractor import (
    ResumeExtractorService,
    UnsupportedFileError,
    CorruptedFileError,
    EncryptedFileError,
    EmptyDocumentError,
    FileSizeLimitExceededError,
)

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    name='candidates.extract_resume_task',
    max_retries=0,  # File extraction issues are generally deterministic; do not retry indefinitely
    soft_time_limit=60,
    time_limit=90,
)
def extract_resume_task(self, operation_id: str, candidate_id: str, expected_fingerprint: str):
    now = timezone.now()

    try:
        operation = AsyncOperation.objects.get(id=operation_id)
    except AsyncOperation.DoesNotExist:
        logger.error(f"AsyncOperation {operation_id} not found.")
        return

    # Update operation to running
    operation.celery_task_id = self.request.id or ''
    operation.status = AsyncOperation.STATUS_RUNNING
    operation.started_at = now
    operation.status_message = "Extracting resume text..."
    operation.attempt_count += 1
    operation.save(update_fields=['celery_task_id', 'status', 'started_at', 'status_message', 'attempt_count'])

    try:
        candidate = Candidate.objects.get(id=candidate_id)
    except Candidate.DoesNotExist:
        operation.status = AsyncOperation.STATUS_FAILED
        operation.status_message = "Candidate record was deleted before processing."
        operation.error_code = "CANDIDATE_NOT_FOUND"
        operation.completed_at = timezone.now()
        operation.save(update_fields=['status', 'status_message', 'error_code', 'completed_at'])
        return

    # Verify resume exists
    if not candidate.resume:
        operation.status = AsyncOperation.STATUS_FAILED
        operation.status_message = "No resume file found on candidate."
        operation.error_code = "RESUME_MISSING"
        operation.completed_at = timezone.now()
        operation.save(update_fields=['status', 'status_message', 'error_code', 'completed_at'])
        return

    # Stale resume check (e.g. file name or version changed after queuing)
    current_fingerprint = f"{candidate.resume.name}:{getattr(candidate.resume, 'size', 0)}"
    if expected_fingerprint and current_fingerprint != expected_fingerprint:
        operation.status = AsyncOperation.STATUS_FAILED
        operation.status_message = "Resume file was modified or replaced after task was enqueued."
        operation.error_code = "STALE_TASK_DETECTED"
        operation.completed_at = timezone.now()
        operation.save(update_fields=['status', 'status_message', 'error_code', 'completed_at'])
        return

    # Call ResumeExtractorService
    try:
        with candidate.resume.open('rb') as f:
            extracted_text = ResumeExtractorService.extract_text(f, candidate.resume.name)
    except UnsupportedFileError as e:
        operation.status = AsyncOperation.STATUS_FAILED
        operation.status_message = str(e)
        operation.error_code = "UNSUPPORTED_FILE_FORMAT"
        operation.completed_at = timezone.now()
        operation.save(update_fields=['status', 'status_message', 'error_code', 'completed_at'])
        return
    except FileSizeLimitExceededError as e:
        operation.status = AsyncOperation.STATUS_FAILED
        operation.status_message = str(e)
        operation.error_code = "FILE_SIZE_LIMIT_EXCEEDED"
        operation.completed_at = timezone.now()
        operation.save(update_fields=['status', 'status_message', 'error_code', 'completed_at'])
        return
    except EncryptedFileError as e:
        operation.status = AsyncOperation.STATUS_FAILED
        operation.status_message = str(e)
        operation.error_code = "DOCUMENT_ENCRYPTED"
        operation.completed_at = timezone.now()
        operation.save(update_fields=['status', 'status_message', 'error_code', 'completed_at'])
        return
    except EmptyDocumentError as e:
        operation.status = AsyncOperation.STATUS_FAILED
        operation.status_message = str(e)
        operation.error_code = "EMPTY_OR_SCANNED_DOCUMENT"
        operation.completed_at = timezone.now()
        operation.save(update_fields=['status', 'status_message', 'error_code', 'completed_at'])
        return
    except CorruptedFileError as e:
        operation.status = AsyncOperation.STATUS_FAILED
        operation.status_message = str(e)
        operation.error_code = "DOCUMENT_CORRUPTED"
        operation.completed_at = timezone.now()
        operation.save(update_fields=['status', 'status_message', 'error_code', 'completed_at'])
        return
    except Exception:
        logger.exception("Unexpected error during resume extraction Celery task.")
        operation.status = AsyncOperation.STATUS_FAILED
        operation.status_message = "Unexpected error during document parsing."
        operation.error_code = "EXTRACTION_FAILED_UNEXPECTED"
        operation.completed_at = timezone.now()
        operation.save(update_fields=['status', 'status_message', 'error_code', 'completed_at'])
        return

    # Success: Save extracted text on Candidate and mark operation succeeded
    candidate.extracted_resume_text = extracted_text
    candidate.save(update_fields=['extracted_resume_text', 'updated_at'])

    operation.status = AsyncOperation.STATUS_SUCCEEDED
    operation.status_message = f"Resume extracted successfully ({len(extracted_text)} characters)."
    operation.completed_at = timezone.now()
    operation.save(update_fields=['status', 'status_message', 'completed_at'])

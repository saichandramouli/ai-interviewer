import logging
from celery import shared_task
from django.db import transaction
from django.utils import timezone
from operations.models import AsyncOperation
from interviews.models import Interview, InterviewQuestion
from interviews.services.question_generator import (
    generate_interview_plan,
    ConfigurationError,
    OpenAIServiceError,
    PlanValidationError,
    QuestionGenerationError,
)

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    name='interviews.generate_plan_task',
    max_retries=2,
    default_retry_delay=10,
    soft_time_limit=75,
    time_limit=100,
)
def generate_plan_task(self, operation_id: str, interview_id: str):
    now = timezone.now()

    try:
        operation = AsyncOperation.objects.get(id=operation_id)
    except AsyncOperation.DoesNotExist:
        logger.error(f"AsyncOperation {operation_id} not found.")
        return

    # Update operation status to running
    operation.celery_task_id = self.request.id or ''
    operation.status = AsyncOperation.STATUS_RUNNING
    operation.started_at = now
    operation.status_message = "Generating structured interview plan via AI..."
    operation.attempt_count += 1
    operation.save(update_fields=['celery_task_id', 'status', 'started_at', 'status_message', 'attempt_count'])

    try:
        interview = Interview.objects.select_related('candidate', 'job').get(id=interview_id)
    except Interview.DoesNotExist:
        operation.status = AsyncOperation.STATUS_FAILED
        operation.status_message = "Interview record was deleted before processing."
        operation.error_code = "INTERVIEW_NOT_FOUND"
        operation.completed_at = timezone.now()
        operation.save(update_fields=['status', 'status_message', 'error_code', 'completed_at'])
        return

    # Validation: Idempotency & existing questions check
    if interview.questions.exists():
        operation.status = AsyncOperation.STATUS_FAILED
        operation.status_message = "Interview plan already contains questions. Overwriting is not permitted."
        operation.error_code = "PLAN_ALREADY_EXISTS"
        operation.completed_at = timezone.now()
        operation.save(update_fields=['status', 'status_message', 'error_code', 'completed_at'])
        return

    if interview.status != Interview.STATUS_DRAFT:
        operation.status = AsyncOperation.STATUS_FAILED
        operation.status_message = f"Interview is not in draft status (current: {interview.status})."
        operation.error_code = "INVALID_INTERVIEW_STATUS"
        operation.completed_at = timezone.now()
        operation.save(update_fields=['status', 'status_message', 'error_code', 'completed_at'])
        return

    resume_text = interview.candidate.extracted_resume_text
    if not resume_text or not resume_text.strip():
        operation.status = AsyncOperation.STATUS_FAILED
        operation.status_message = "Candidate resume text has not been extracted."
        operation.error_code = "MISSING_RESUME_TEXT"
        operation.completed_at = timezone.now()
        operation.save(update_fields=['status', 'status_message', 'error_code', 'completed_at'])
        return

    job_desc = interview.job.description
    if not job_desc or not job_desc.strip():
        operation.status = AsyncOperation.STATUS_FAILED
        operation.status_message = "Job description is empty."
        operation.error_code = "MISSING_JOB_DESCRIPTION"
        operation.completed_at = timezone.now()
        operation.save(update_fields=['status', 'status_message', 'error_code', 'completed_at'])
        return

    # Call QuestionGeneratorService with bounded retry for transient network/rate-limit errors
    try:
        plan = generate_interview_plan(
            resume_text=resume_text,
            job_title=interview.job.title,
            job_description=interview.job.description,
            required_skills=interview.job.required_skills,
            experience_requirements=interview.job.experience_requirements,
        )
    except ConfigurationError as e:
        # Permanent failure (missing key/model) - do NOT retry
        operation.status = AsyncOperation.STATUS_FAILED
        operation.status_message = str(e)
        operation.error_code = "AI_CONFIGURATION_MISSING"
        operation.completed_at = timezone.now()
        operation.save(update_fields=['status', 'status_message', 'error_code', 'completed_at'])
        return
    except PlanValidationError as e:
        # Schema / content validation error - do NOT retry
        operation.status = AsyncOperation.STATUS_FAILED
        operation.status_message = str(e)
        operation.error_code = "AI_PLAN_VALIDATION_FAILED"
        operation.completed_at = timezone.now()
        operation.save(update_fields=['status', 'status_message', 'error_code', 'completed_at'])
        return
    except OpenAIServiceError as e:
        # Transient network / rate limit error - apply bounded retry up to max_retries
        logger.warning(f"Transient AI service error: {e}. Retrying task ({self.request.retries}/{self.max_retries})...")
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e)
        else:
            operation.status = AsyncOperation.STATUS_FAILED
            operation.status_message = "AI service temporarily unavailable after retries. Please retry later."
            operation.error_code = "AI_SERVICE_UNAVAILABLE"
            operation.completed_at = timezone.now()
            operation.save(update_fields=['status', 'status_message', 'error_code', 'completed_at'])
            return
    except Exception as e:
        logger.exception("Unexpected error during plan generation Celery task.")
        operation.status = AsyncOperation.STATUS_FAILED
        operation.status_message = "Unexpected error generating interview plan."
        operation.error_code = "PLAN_GENERATION_FAILED_UNEXPECTED"
        operation.completed_at = timezone.now()
        operation.save(update_fields=['status', 'status_message', 'error_code', 'completed_at'])
        return

    # Persist plan and questions atomically
    try:
        with transaction.atomic():
            # Double check inside atomic lock to ensure no race condition created questions
            interview.refresh_from_db()
            if interview.questions.exists():
                operation.status = AsyncOperation.STATUS_FAILED
                operation.status_message = "Interview plan was already saved by another concurrent request."
                operation.error_code = "CONCURRENT_CONFLICT"
                operation.completed_at = timezone.now()
                operation.save(update_fields=['status', 'status_message', 'error_code', 'completed_at'])
                return

            interview.plan_data = {
                "introduction": plan.introduction,
                "closing_statement": plan.closing_statement,
                "total_estimated_minutes": plan.total_estimated_minutes,
            }
            interview.save(update_fields=['plan_data', 'updated_at'])

            question_objects = [
                InterviewQuestion(
                    interview=interview,
                    sequence_number=q.sequence_number,
                    question_text=q.question_text,
                    category=q.category,
                    competency=q.competency,
                    expected_evidence=q.expected_evidence,
                    suggested_follow_up=q.suggested_follow_up,
                    estimated_minutes=q.estimated_minutes,
                    max_score=q.max_score,
                )
                for q in plan.questions
            ]
            InterviewQuestion.objects.bulk_create(question_objects)

    except Exception as e:
        logger.exception("Failed to atomically persist generated interview plan.")
        operation.status = AsyncOperation.STATUS_FAILED
        operation.status_message = "Failed to store generated plan in database."
        operation.error_code = "DATABASE_PERSISTENCE_ERROR"
        operation.completed_at = timezone.now()
        operation.save(update_fields=['status', 'status_message', 'error_code', 'completed_at'])
        return

    # Mark operation succeeded
    operation.status = AsyncOperation.STATUS_SUCCEEDED
    operation.status_message = f"Interview plan generated successfully with {len(plan.questions)} questions."
    operation.completed_at = timezone.now()
    operation.save(update_fields=['status', 'status_message', 'completed_at'])

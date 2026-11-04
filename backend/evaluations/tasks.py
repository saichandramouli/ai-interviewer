import logging
from celery import shared_task
from django.db import transaction
from django.utils import timezone

from interviews.models import Interview
from evaluations.models import EvaluationResult
from evaluations.services.evaluation_service import (
    EvaluationService,
    EvaluationServiceError,
    EvaluationAPIError,
    EvaluationValidationError,
)

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    name='evaluations.generate_evaluation_task',
    max_retries=3,
    default_retry_delay=15,
    soft_time_limit=120,
    time_limit=150,
)
def generate_evaluation_task(self, interview_id: str):
    """
    Asynchronous Celery task to evaluate a completed interview using NVIDIA Nemotron.
    Enforces idempotency, concurrency locks, and bounded retry on transient failures.
    """
    logger.info("Evaluation task initiated for interview_id=%s (attempt=%d)", interview_id, self.request.retries)

    try:
        interview = Interview.objects.select_related('candidate', 'job').get(id=interview_id)
    except Interview.DoesNotExist:
        logger.error("Interview %s does not exist. Halting evaluation task.", interview_id)
        return

    # Eligibility check: only completed interviews are evaluated
    if interview.status != Interview.STATUS_COMPLETED:
        logger.warning(
            "Interview %s is not in completed status (current: %s). Skipping evaluation.",
            interview_id,
            interview.status
        )
        return

    # Idempotency & Concurrency Check
    with transaction.atomic():
        eval_obj, created = EvaluationResult.objects.select_for_update().get_or_create(
            interview=interview,
            defaults={
                "evaluation_status": EvaluationResult.EVAL_STATUS_PROCESSING,
            }
        )

        # If already completed or reviewed, do not overwrite
        if not created:
            if eval_obj.review_status == EvaluationResult.STATUS_REVIEWED:
                logger.info("Evaluation for interview %s was already reviewed by recruiter. Skipping overwrite.", interview_id)
                return
            if eval_obj.evaluation_status == EvaluationResult.EVAL_STATUS_COMPLETED:
                logger.info("Evaluation for interview %s is already completed. Skipping redundant task.", interview_id)
                return
            if eval_obj.evaluation_status == EvaluationResult.EVAL_STATUS_PROCESSING and self.request.retries == 0:
                logger.info("Evaluation for interview %s is currently processing in another worker. Skipping.", interview_id)
                return

            # Mark as processing for this attempt
            eval_obj.evaluation_status = EvaluationResult.EVAL_STATUS_PROCESSING
            eval_obj.save(update_fields=['evaluation_status'])

    # Run AI evaluation service outside the long database lock
    service = EvaluationService()
    try:
        eval_result = service.evaluate_interview(interview)
        logger.info(
            "Evaluation successfully generated for interview_id=%s with overall_score=%s",
            interview_id,
            eval_result.overall_score
        )
    except EvaluationAPIError as err:
        # Transient network / rate limit / 5xx error -> bounded retry
        logger.warning("Transient NVIDIA API error for interview %s: %s", interview_id, str(err))
        if self.request.retries < self.max_retries:
            try:
                raise self.retry(exc=err, countdown=15 * (2 ** self.request.retries))
            except Exception:
                raise
        else:
            logger.error("Max retries exceeded for interview %s. Marking evaluation failed.", interview_id)
            EvaluationResult.objects.filter(interview=interview).update(
                evaluation_status=EvaluationResult.EVAL_STATUS_FAILED,
                error_message=f"Evaluation service unavailable: {str(err)[:200]}",
            )
    except (EvaluationValidationError, EvaluationServiceError) as err:
        # Permanent validation or logic failure -> do NOT retry infinitely
        logger.error("Non-retryable evaluation error for interview %s: %s", interview_id, str(err))
        EvaluationResult.objects.filter(interview=interview).update(
            evaluation_status=EvaluationResult.EVAL_STATUS_FAILED,
            error_message=f"Evaluation failed: {str(err)[:200]}",
        )
    except Exception as err:
        logger.exception("Unexpected error during evaluation for interview %s", interview_id)
        EvaluationResult.objects.filter(interview=interview).update(
            evaluation_status=EvaluationResult.EVAL_STATUS_FAILED,
            error_message="Unexpected internal error during evaluation.",
        )


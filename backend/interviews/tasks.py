import logging
from datetime import timedelta
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


@shared_task(
    bind=True,
    name='interviews.send_candidate_invitation_email_task',
    max_retries=3,
    default_retry_delay=15,
    soft_time_limit=60,
    time_limit=90,
)
def send_candidate_invitation_email_task(
    self,
    token_id: int,
    candidate_url: str,
):
    """
    Asynchronously delivers the candidate interview invitation email via Django's configured EmailBackend.
    Ensures idempotency, bounded retry with backoff, and sanitized failure tracking.
    """
    from django.core.mail import EmailMultiAlternatives
    from interviews.models import CandidateInterviewAccessToken
    from interviews.services.email_service import (
        build_candidate_invitation_subject,
        build_candidate_invitation_body,
        build_candidate_invitation_html,
    )

    logger.info("Sending candidate invitation email for token_id=%s (attempt=%d)", token_id, self.request.retries)

    now = timezone.now()
    lease_cutoff = now - timedelta(seconds=180)  # 3 minutes bounded lease for crashed workers

    # 1. Atomic task claiming with row-level lock
    with transaction.atomic():
        try:
            token_obj = CandidateInterviewAccessToken.objects.select_for_update().select_related(
                'interview', 'interview__candidate', 'interview__job', 'interview__created_by'
            ).get(id=token_id)
        except CandidateInterviewAccessToken.DoesNotExist:
            logger.error("CandidateInterviewAccessToken %s not found. Aborting email task.", token_id)
            return

        # Guard: Check if token is revoked or expired
        if token_obj.is_revoked or now >= token_obj.expires_at:
            logger.warning("Token %s is revoked or expired. Aborting email delivery.", token_id)
            token_obj.delivery_status = CandidateInterviewAccessToken.DELIVERY_FAILED
            token_obj.delivery_error = "Token is expired or has been revoked."
            token_obj.save(update_fields=['delivery_status', 'delivery_error'])
            return

        # Guard: Deduplication check - already delivered
        if token_obj.delivery_status == CandidateInterviewAccessToken.DELIVERY_SENT:
            logger.info("Invitation for token %s was already delivered. Skipping duplicate send.", token_id)
            return

        # Guard: Concurrent worker execution check
        if token_obj.delivery_status == CandidateInterviewAccessToken.DELIVERY_SENDING:
            # Check lease to see if previous worker crashed
            if token_obj.delivery_started_at and token_obj.delivery_started_at > lease_cutoff:
                logger.info(
                    "Token %s is currently being sent by another worker with active lease. Exiting gracefully.",
                    token_id
                )
                return
            else:
                logger.warning(
                    "Token %s had an expired sending lease (started at %s). Re-claiming task.",
                    token_id, token_obj.delivery_started_at
                )

        # Candidate email check
        candidate = token_obj.interview.candidate
        recipient_email = candidate.email
        if not recipient_email or not recipient_email.strip():
            logger.error("Candidate %s has no email address. Marking delivery failed.", candidate.id)
            token_obj.delivery_status = CandidateInterviewAccessToken.DELIVERY_FAILED
            token_obj.delivery_error = "Candidate record has no registered email address."
            token_obj.save(update_fields=['delivery_status', 'delivery_error'])
            return

        # Successfully claim task
        token_obj.delivery_status = CandidateInterviewAccessToken.DELIVERY_SENDING
        token_obj.delivery_started_at = now
        token_obj.recipient_email = recipient_email
        token_obj.save(update_fields=['delivery_status', 'delivery_started_at', 'recipient_email'])

    # Transaction is committed; locks are released BEFORE invoking external email service!

    job = token_obj.interview.job
    org_name = getattr(token_obj.interview.created_by, 'organization_name', None) or "Hiring Team"
    expires_str = token_obj.expires_at.strftime("%B %d, %Y at %I:%M %p UTC")

    # If candidate_url was not supplied as argument, decrypt from encrypted_candidate_url
    if not candidate_url and token_obj.encrypted_candidate_url:
        from interviews.services.token_crypto import decrypt_url
        candidate_url = decrypt_url(token_obj.encrypted_candidate_url)

    if not candidate_url:
        logger.error("No valid candidate URL available for token %s. Delivery aborted.", token_id)
        with transaction.atomic():
            tok = CandidateInterviewAccessToken.objects.select_for_update().get(id=token_id)
            tok.delivery_status = CandidateInterviewAccessToken.DELIVERY_FAILED
            tok.delivery_error = "Missing candidate URL."
            tok.save(update_fields=['delivery_status', 'delivery_error'])
        return

    subject = build_candidate_invitation_subject(job.title)
    text_content = build_candidate_invitation_body(
        candidate_name=candidate.full_name,
        job_title=job.title,
        organization_name=org_name,
        candidate_url=candidate_url,
        expires_at_str=expires_str,
    )
    html_content = build_candidate_invitation_html(
        candidate_name=candidate.full_name,
        job_title=job.title,
        organization_name=org_name,
        candidate_url=candidate_url,
        expires_at_str=expires_str,
    )

    try:
        msg = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            to=[recipient_email],
        )
        msg.attach_alternative(html_content, "text/html")
        msg.send(fail_silently=False)

        # Mark sent atomically
        with transaction.atomic():
            tok = CandidateInterviewAccessToken.objects.select_for_update().get(id=token_id)
            tok.delivery_status = CandidateInterviewAccessToken.DELIVERY_SENT
            tok.sent_at = timezone.now()
            tok.delivery_error = ""
            tok.save(update_fields=['delivery_status', 'sent_at', 'delivery_error'])
        logger.info("Candidate invitation email successfully delivered to %s (token_id=%s)", recipient_email, token_id)

    except Exception as exc:
        logger.warning("Failed to send candidate email (token_id=%s): %s", token_id, str(exc))
        with transaction.atomic():
            tok = CandidateInterviewAccessToken.objects.select_for_update().get(id=token_id)
            if self.request.retries < self.max_retries:
                tok.delivery_status = CandidateInterviewAccessToken.DELIVERY_PENDING
                tok.delivery_error = "Temporary delivery failure, retrying..."
                tok.save(update_fields=['delivery_status', 'delivery_error'])
            else:
                tok.delivery_status = CandidateInterviewAccessToken.DELIVERY_FAILED
                tok.delivery_error = "Email provider delivery failed after multiple attempts."
                tok.save(update_fields=['delivery_status', 'delivery_error'])

        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=15 * (2 ** self.request.retries))
        else:
            logger.error("Max retries exceeded for email delivery (token_id=%s).", token_id)

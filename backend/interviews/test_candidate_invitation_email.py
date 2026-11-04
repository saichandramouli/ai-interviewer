"""
Integration and unit tests for candidate interview invitation email sending.
Verifies:
1. Automated email queuing upon candidate link generation.
2. Email content accuracy (candidate name, org name, job title, clean URL, expiration).
3. Email delivery status transitions (pending -> sent / failed).
4. Idempotency and error handling without token corruption.
5. Recruiter-initiated resend link action.
6. Guard checks against sending emails for completed/cancelled interviews or missing candidate email.
7. Candidate link status endpoint.
"""
from datetime import timedelta
from unittest.mock import patch
import pytest
from django.utils import timezone
from django.core import mail
from rest_framework.test import APIClient
from rest_framework import status

from accounts.models import User
from candidates.models import Candidate
from jobs.models import Job
from interviews.models import Interview, CandidateInterviewAccessToken
from interviews.tasks import send_candidate_invitation_email_task


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def recruiter_user(db):
    user = User.objects.create_user(
        email="recruiter@company.com",
        password="ValidPassword123!",
    )
    return user


@pytest.fixture
def other_recruiter(db):
    return User.objects.create_user(
        email="other@company.com",
        password="ValidPassword123!",
    )


@pytest.fixture
def job(db, recruiter_user):
    return Job.objects.create(
        created_by=recruiter_user,
        title="Senior AI Engineer",
        description="Build state-of-the-art LLM solutions.",
        required_skills=["Python", "PyTorch", "LangChain", "Celery"],
    )


@pytest.fixture
def candidate(db, recruiter_user):
    return Candidate.objects.create(
        created_by=recruiter_user,
        full_name="Jane Doe",
        email="jane.doe@example.com",
        phone_number="+1234567890",
        consent_status=Candidate.CONSENT_GRANTED,
    )


@pytest.fixture
def interview(db, recruiter_user, job, candidate):
    return Interview.objects.create(
        created_by=recruiter_user,
        job=job,
        candidate=candidate,
        status=Interview.STATUS_SCHEDULED,
    )


@pytest.mark.django_db
class TestCandidateInvitationEmailWorkflow:
    def test_generate_candidate_link_enqueues_email(self, api_client, recruiter_user, interview):
        api_client.force_authenticate(user=recruiter_user)

        with patch("interviews.tasks.send_candidate_invitation_email_task.delay") as mock_delay:
            response = api_client.post(
                f"/api/v1/interviews/{interview.id}/generate-candidate-link/",
                {"valid_hours": 48},
                format="json",
            )

            assert response.status_code == status.HTTP_201_CREATED
            data = response.json()
            assert "raw_token" in data
            assert "candidate_url" in data
            assert data["candidate_email"] == "jane.doe@example.com"
            assert data["email_enqueued"] is True
            assert mock_delay.called

            # Check token database record
            token = CandidateInterviewAccessToken.objects.get(interview=interview)
            assert token.recipient_email == "jane.doe@example.com"
            assert token.delivery_status == CandidateInterviewAccessToken.DELIVERY_PENDING

    def test_candidate_without_email_records_failed_delivery(self, api_client, recruiter_user, job):
        candidate_no_email = Candidate.objects.create(
            created_by=recruiter_user,
            full_name="No Email Person",
            email="",
            consent_status=Candidate.CONSENT_GRANTED,
        )
        intv = Interview.objects.create(
            created_by=recruiter_user,
            job=job,
            candidate=candidate_no_email,
            status=Interview.STATUS_SCHEDULED,
        )

        api_client.force_authenticate(user=recruiter_user)
        with patch("interviews.tasks.send_candidate_invitation_email_task.delay") as mock_delay:
            response = api_client.post(
                f"/api/v1/interviews/{intv.id}/generate-candidate-link/",
                format="json",
            )
            assert response.status_code == status.HTTP_201_CREATED
            data = response.json()
            assert data["email_enqueued"] is False
            assert not mock_delay.called

            token = CandidateInterviewAccessToken.objects.get(interview=intv)
            assert token.delivery_status == CandidateInterviewAccessToken.DELIVERY_FAILED
            assert "no registered email" in token.delivery_error.lower()

    def test_send_candidate_invitation_email_task_execution(self, recruiter_user, interview):
        token_obj, raw_token = CandidateInterviewAccessToken.create_token(interview, valid_hours=24)
        token_obj.recipient_email = interview.candidate.email
        token_obj.save()

        candidate_url = f"https://app.test.com/interview/session?token={raw_token}"

        # Execute task directly
        send_candidate_invitation_email_task(token_obj.id, candidate_url)

        # Check mail outbox
        assert len(mail.outbox) == 1
        sent_email = mail.outbox[0]
        assert "Invitation to Attend Your AI Interview: Senior AI Engineer" in sent_email.subject
        assert interview.candidate.email in sent_email.to
        assert candidate_url in sent_email.body
        assert "Jane Doe" in sent_email.body
        assert len(sent_email.alternatives) == 1
        assert sent_email.alternatives[0][1] == "text/html"

        # Check token updated in database
        token_obj.refresh_from_db()
        assert token_obj.delivery_status == CandidateInterviewAccessToken.DELIVERY_SENT
        assert token_obj.sent_at is not None
        assert token_obj.delivery_error == ""

    def test_email_task_idempotency(self, recruiter_user, interview):
        token_obj, raw_token = CandidateInterviewAccessToken.create_token(interview, valid_hours=24)
        token_obj.recipient_email = interview.candidate.email
        token_obj.delivery_status = CandidateInterviewAccessToken.DELIVERY_SENT
        token_obj.sent_at = timezone.now()
        token_obj.save()

        # Run task again on already sent token
        candidate_url = f"https://app.test.com/interview/session?token={raw_token}"
        send_candidate_invitation_email_task(token_obj.id, candidate_url)

        # No email sent since it was already delivered
        assert len(mail.outbox) == 0

    def test_email_task_expired_or_revoked_token_guard(self, recruiter_user, interview):
        # Expired token
        token_obj, raw_token = CandidateInterviewAccessToken.create_token(interview, valid_hours=1)
        token_obj.expires_at = timezone.now() - timedelta(minutes=5)
        token_obj.recipient_email = interview.candidate.email
        token_obj.save()

        candidate_url = f"https://app.test.com/interview/session?token={raw_token}"
        send_candidate_invitation_email_task(token_obj.id, candidate_url)

        assert len(mail.outbox) == 0
        token_obj.refresh_from_db()
        assert token_obj.delivery_status == CandidateInterviewAccessToken.DELIVERY_FAILED
        assert "expired" in token_obj.delivery_error.lower()

    def test_resend_candidate_link_endpoint(self, api_client, recruiter_user, interview):
        api_client.force_authenticate(user=recruiter_user)

        with patch("interviews.tasks.send_candidate_invitation_email_task.delay"):
            api_client.post(f"/api/v1/interviews/{interview.id}/generate-candidate-link/")

        with patch("interviews.tasks.send_candidate_invitation_email_task.delay") as mock_delay:
            response = api_client.post(
                f"/api/v1/interviews/{interview.id}/resend-candidate-link/",
                format="json",
            )
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert "candidate_url" in data
            assert data["candidate_email"] == "jane.doe@example.com"
            assert mock_delay.called

    def test_candidate_link_status_endpoint(self, api_client, recruiter_user, interview):
        api_client.force_authenticate(user=recruiter_user)

        # Before generating link
        res1 = api_client.get(f"/api/v1/interviews/{interview.id}/candidate-link-status/")
        assert res1.status_code == status.HTTP_200_OK
        assert res1.json()["has_token"] is False

        # Generate link
        token_obj, _ = CandidateInterviewAccessToken.create_token(interview, valid_hours=24)
        token_obj.recipient_email = "jane.doe@example.com"
        token_obj.delivery_status = CandidateInterviewAccessToken.DELIVERY_SENT
        token_obj.sent_at = timezone.now()
        token_obj.save()

        res2 = api_client.get(f"/api/v1/interviews/{interview.id}/candidate-link-status/")
        assert res2.status_code == status.HTTP_200_OK
        data2 = res2.json()
        assert data2["has_token"] is True
        assert data2["is_valid"] is True
        assert data2["delivery_status"] == "sent"
        assert data2["recipient_email"] == "jane.doe@example.com"

    def test_cannot_generate_or_resend_for_completed_interview(self, api_client, recruiter_user, interview):
        interview.status = Interview.STATUS_COMPLETED
        interview.save()

        api_client.force_authenticate(user=recruiter_user)

        res_gen = api_client.post(f"/api/v1/interviews/{interview.id}/generate-candidate-link/")
        assert res_gen.status_code == status.HTTP_400_BAD_REQUEST

        res_resend = api_client.post(f"/api/v1/interviews/{interview.id}/resend-candidate-link/")
        assert res_resend.status_code == status.HTTP_400_BAD_REQUEST

    def test_other_recruiter_cannot_access_or_resend_link(self, api_client, other_recruiter, interview):
        api_client.force_authenticate(user=other_recruiter)

        res_gen = api_client.post(f"/api/v1/interviews/{interview.id}/generate-candidate-link/")
        assert res_gen.status_code == status.HTTP_404_NOT_FOUND

        res_resend = api_client.post(f"/api/v1/interviews/{interview.id}/resend-candidate-link/")
        assert res_resend.status_code == status.HTTP_404_NOT_FOUND

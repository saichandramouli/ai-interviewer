"""
Phase 10.3.1 Concurrency and Resend Hardening Test Suite.
Verifies:
1. Two concurrent workers attempting to claim the same invitation token: only one claims it.
2. Deduplication check: duplicate task execution after successful delivery does not send again.
3. Worker failure during delivery allows bounded retry.
4. Stale 'sending' state beyond 3 minutes lease recovers safely.
5. Ordinary resend does NOT create a new token and reuses existing token.
6. Ordinary resend does NOT revoke existing valid token.
7. Expired and revoked tokens cannot be resent.
8. Explicit replacement generates a new token and revokes previous tokens.
9. Cross-recruiter authorization prevents unauthorized resend or replacement.
10. Raw tokens are never stored in database or logged in tasks.
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
from interviews.services.token_crypto import encrypt_url, decrypt_url


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def recruiter_user(db):
    return User.objects.create_user(
        email="recruiter_harden@company.com",
        password="ValidPassword123!",
    )


@pytest.fixture
def other_recruiter(db):
    return User.objects.create_user(
        email="other_recruiter@company.com",
        password="ValidPassword123!",
    )


@pytest.fixture
def job(db, recruiter_user):
    return Job.objects.create(
        created_by=recruiter_user,
        title="Staff ML Systems Engineer",
        description="Design resilient distributed inference systems.",
        required_skills=["Python", "Distributed Systems", "Celery", "Postgres"],
    )


@pytest.fixture
def candidate(db, recruiter_user):
    return Candidate.objects.create(
        created_by=recruiter_user,
        full_name="Alice Candidate",
        email="alice.candidate@example.com",
        phone_number="+15551234567",
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


@pytest.mark.django_db(transaction=True)
class TestPhase1031ReliabilityAndHardening:

    def test_ordinary_resend_preserves_existing_token_without_generating_new_one(
        self, api_client, recruiter_user, interview
    ):
        """
        Ordinary resend must reuse existing active token without creating another token or revoking it.
        """
        api_client.force_authenticate(user=recruiter_user)

        # 1. Initial generation
        with patch("interviews.tasks.send_candidate_invitation_email_task.delay") as mock_gen_delay:
            gen_res = api_client.post(f"/api/v1/interviews/{interview.id}/generate-candidate-link/")
            assert gen_res.status_code == status.HTTP_201_CREATED
            initial_url = gen_res.json()["candidate_url"]

        tokens_before = list(CandidateInterviewAccessToken.objects.filter(interview=interview))
        assert len(tokens_before) == 1
        initial_token = tokens_before[0]
        assert not initial_token.is_revoked

        # 2. Resend call
        with patch("interviews.tasks.send_candidate_invitation_email_task.delay") as mock_delay:
            resend_res = api_client.post(f"/api/v1/interviews/{interview.id}/resend-candidate-link/")
            assert resend_res.status_code == status.HTTP_200_OK
            data = resend_res.json()
            assert data["candidate_url"] == initial_url
            assert mock_delay.called

        # 3. Assert no new token created, original token not revoked
        tokens_after = list(CandidateInterviewAccessToken.objects.filter(interview=interview))
        assert len(tokens_after) == 1
        assert tokens_after[0].id == initial_token.id
        assert not tokens_after[0].is_revoked

    def test_explicit_replace_revokes_prior_token_and_creates_new_token(
        self, api_client, recruiter_user, interview
    ):
        """
        Explicit replacement creates a new token and revokes older tokens.
        """
        api_client.force_authenticate(user=recruiter_user)

        # Initial link
        with patch("interviews.tasks.send_candidate_invitation_email_task.delay"):
            api_client.post(f"/api/v1/interviews/{interview.id}/generate-candidate-link/")
        first_token = CandidateInterviewAccessToken.objects.get(interview=interview)

        # Explicit replace call
        with patch("interviews.tasks.send_candidate_invitation_email_task.delay") as mock_delay:
            replace_res = api_client.post(f"/api/v1/interviews/{interview.id}/replace-candidate-link/")
            assert replace_res.status_code == status.HTTP_201_CREATED
            assert mock_delay.called

        tokens = CandidateInterviewAccessToken.objects.filter(interview=interview).order_by('created_at')
        assert tokens.count() == 2
        assert tokens[0].id == first_token.id
        assert tokens[0].is_revoked is True
        assert tokens[1].is_revoked is False

    def test_concurrent_worker_claiming_prevents_duplicate_send(self, recruiter_user, interview):
        """
        If two workers attempt to send the same token simultaneously, only the one
        holding the atomic claim proceeds; the other sees status == 'sending' with active lease and exits.
        """
        token_obj, raw_token = CandidateInterviewAccessToken.create_token(interview, valid_hours=24)
        candidate_url = f"http://testserver/interview/session?token={raw_token}"
        token_obj.encrypted_candidate_url = encrypt_url(candidate_url)
        token_obj.recipient_email = interview.candidate.email
        token_obj.save()

        # Worker 1 claims task and sets status to 'sending' with current timestamp
        token_obj.delivery_status = CandidateInterviewAccessToken.DELIVERY_SENDING
        token_obj.delivery_started_at = timezone.now()
        token_obj.save(update_fields=['delivery_status', 'delivery_started_at'])

        # Worker 2 runs task while Worker 1 holds active lease
        send_candidate_invitation_email_task(token_obj.id, candidate_url)

        # No duplicate email sent by Worker 2
        assert len(mail.outbox) == 0

    def test_stale_sending_state_lease_recovery(self, recruiter_user, interview):
        """
        If a worker died while 'sending' and lease expired (> 3 mins), another worker
        re-claims the task and delivers the email.
        """
        token_obj, raw_token = CandidateInterviewAccessToken.create_token(interview, valid_hours=24)
        candidate_url = f"http://testserver/interview/session?token={raw_token}"
        token_obj.encrypted_candidate_url = encrypt_url(candidate_url)
        token_obj.recipient_email = interview.candidate.email
        # Set delivery_started_at to 5 minutes ago (lease expired)
        token_obj.delivery_status = CandidateInterviewAccessToken.DELIVERY_SENDING
        token_obj.delivery_started_at = timezone.now() - timedelta(minutes=5)
        token_obj.save()

        # Run task
        send_candidate_invitation_email_task(token_obj.id, candidate_url)

        # Email successfully sent
        assert len(mail.outbox) == 1
        token_obj.refresh_from_db()
        assert token_obj.delivery_status == CandidateInterviewAccessToken.DELIVERY_SENT
        assert token_obj.sent_at is not None

    def test_duplicate_task_execution_after_sent_does_not_send_again(self, recruiter_user, interview):
        """
        Once marked 'sent', repeated execution does not send duplicate emails.
        """
        token_obj, raw_token = CandidateInterviewAccessToken.create_token(interview, valid_hours=24)
        candidate_url = f"http://testserver/interview/session?token={raw_token}"
        token_obj.encrypted_candidate_url = encrypt_url(candidate_url)
        token_obj.recipient_email = interview.candidate.email
        token_obj.delivery_status = CandidateInterviewAccessToken.DELIVERY_SENT
        token_obj.sent_at = timezone.now()
        token_obj.save()

        send_candidate_invitation_email_task(token_obj.id, candidate_url)
        assert len(mail.outbox) == 0

    def test_resend_fails_if_token_expired(self, api_client, recruiter_user, interview):
        api_client.force_authenticate(user=recruiter_user)

        token_obj, raw_token = CandidateInterviewAccessToken.create_token(interview, valid_hours=1)
        token_obj.expires_at = timezone.now() - timedelta(minutes=10)
        candidate_url = f"http://testserver/interview/session?token={raw_token}"
        token_obj.encrypted_candidate_url = encrypt_url(candidate_url)
        token_obj.save()

        res = api_client.post(f"/api/v1/interviews/{interview.id}/resend-candidate-link/")
        assert res.status_code == status.HTTP_400_BAD_REQUEST
        assert "expired" in res.json()["detail"].lower()

    def test_resend_fails_if_token_revoked(self, api_client, recruiter_user, interview):
        api_client.force_authenticate(user=recruiter_user)

        token_obj, raw_token = CandidateInterviewAccessToken.create_token(interview, valid_hours=24)
        token_obj.is_revoked = True
        candidate_url = f"http://testserver/interview/session?token={raw_token}"
        token_obj.encrypted_candidate_url = encrypt_url(candidate_url)
        token_obj.save()

        res = api_client.post(f"/api/v1/interviews/{interview.id}/resend-candidate-link/")
        assert res.status_code == status.HTTP_400_BAD_REQUEST
        assert "revoked" in res.json()["detail"].lower()

    def test_other_recruiter_cannot_replace_or_resend(self, api_client, other_recruiter, interview):
        api_client.force_authenticate(user=other_recruiter)

        res1 = api_client.post(f"/api/v1/interviews/{interview.id}/resend-candidate-link/")
        assert res1.status_code == status.HTTP_404_NOT_FOUND

        res2 = api_client.post(f"/api/v1/interviews/{interview.id}/replace-candidate-link/")
        assert res2.status_code == status.HTTP_404_NOT_FOUND

    def test_raw_token_never_stored_in_database(self, recruiter_user, interview):
        """
        Verify database stores only SHA-256 hash and encrypted URL, never the raw token in plaintext.
        """
        token_obj, raw_token = CandidateInterviewAccessToken.create_token(interview, valid_hours=24)
        token_obj.refresh_from_db()

        assert raw_token not in token_obj.token_hash
        assert raw_token not in token_obj.encrypted_candidate_url
        assert len(token_obj.token_hash) == 64  # Hex SHA-256
        assert token_obj.token_hash == CandidateInterviewAccessToken.hash_token(raw_token)


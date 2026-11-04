import json
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import User
from candidates.models import Candidate
from jobs.models import Job
from interviews.models import Interview, InterviewQuestion, TranscriptEntry
from evaluations.models import EvaluationResult


class Phase10_2_RecruiterReviewTests(TestCase):
    def setUp(self):
        self.client = APIClient()

        # Create Recruiters
        self.recruiter1 = User.objects.create_user(
            email="recruiter1_p10_2@example.com",
            password="Password123!",
            first_name="Alice",
            last_name="Recruiter",
        )
        self.recruiter2 = User.objects.create_user(
            email="recruiter2_p10_2@example.com",
            password="Password123!",
            first_name="Bob",
            last_name="Recruiter",
        )

        # JWT Token for Recruiter 1
        resp = self.client.post("/api/v1/auth/token/", {
            "email": "recruiter1_p10_2@example.com",
            "password": "Password123!",
        })
        self.r1_token = resp.json()["access"]
        self.r1_auth = {"HTTP_AUTHORIZATION": f"Bearer {self.r1_token}"}

        # JWT Token for Recruiter 2
        resp2 = self.client.post("/api/v1/auth/token/", {
            "email": "recruiter2_p10_2@example.com",
            "password": "Password123!",
        })
        self.r2_token = resp2.json()["access"]
        self.r2_auth = {"HTTP_AUTHORIZATION": f"Bearer {self.r2_token}"}

        # Create Candidate & Job
        self.candidate = Candidate.objects.create(
            created_by=self.recruiter1,
            full_name="Samantha Ray",
            email="samantha@example.com",
            consent_status=Candidate.CONSENT_GRANTED,
            extracted_resume_text="Senior React and Node engineer."
        )
        self.job = Job.objects.create(
            created_by=self.recruiter1,
            title="Senior Frontend Engineer",
            description="Build scalable client interfaces.",
            required_skills=["React", "TypeScript", "Vite"],
            experience_requirements="4+ years frontend development",
        )

        # Create Completed Interview
        self.interview = Interview.objects.create(
            created_by=self.recruiter1,
            candidate=self.candidate,
            job=self.job,
            status=Interview.STATUS_COMPLETED,
            started_at=timezone.now(),
            ended_at=timezone.now(),
            plan_data={"introduction": "Welcome.", "closing_statement": "Thanks."},
        )

        # Create EvaluationResult
        self.evaluation = EvaluationResult.objects.create(
            interview=self.interview,
            overall_score=84.0,
            competency_scores={"React": 85.0, "Architecture": 83.0},
            strengths=["Strong understanding of React component lifecycle."],
            improvement_areas=["Could optimize bundle splitting."],
            evidence_summary="Candidate demonstrated solid frontend engineering skills.",
            evaluation_status=EvaluationResult.EVAL_STATUS_COMPLETED,
            review_status=EvaluationResult.STATUS_PENDING,
        )

    # --- 1. Recruiter Review Endpoint Tests ---

    def test_recruiter_can_submit_hire_decision(self):
        """Owning recruiter records 'hire' decision with review notes."""
        url = f"/api/v1/interviews/{self.interview.id}/evaluation/review/"
        payload = {
            "final_decision": "hire",
            "recruiter_notes": "Candidate excelled at core technical questions. Recommend hiring.",
        }
        resp = self.client.patch(url, payload, format="json", **self.r1_auth)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["final_decision"], "hire")
        self.assertEqual(data["review_status"], "reviewed")
        self.assertEqual(data["recruiter_notes"], payload["recruiter_notes"])
        self.assertEqual(data["reviewed_by_email"], self.recruiter1.email)
        self.assertIsNotNone(data["reviewed_at"])

    def test_recruiter_can_submit_hold_decision(self):
        """Owning recruiter records 'hold' decision."""
        url = f"/api/v1/interviews/{self.interview.id}/evaluation/review/"
        resp = self.client.patch(url, {"final_decision": "hold", "recruiter_notes": "Hold for team sync."}, format="json", **self.r1_auth)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["final_decision"], "hold")

    def test_recruiter_can_submit_reject_decision(self):
        """Owning recruiter records 'reject' decision."""
        url = f"/api/v1/interviews/{self.interview.id}/evaluation/review/"
        resp = self.client.patch(url, {"final_decision": "reject", "recruiter_notes": "Not enough seniority."}, format="json", **self.r1_auth)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["final_decision"], "reject")

    def test_invalid_decision_rejected(self):
        """Invalid decision options return HTTP 400."""
        url = f"/api/v1/interviews/{self.interview.id}/evaluation/review/"
        resp = self.client.patch(url, {"final_decision": "maybe"}, format="json", **self.r1_auth)
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["error_code"], "INVALID_DECISION")

    def test_long_notes_rejected(self):
        """Notes exceeding 5000 characters return HTTP 400."""
        url = f"/api/v1/interviews/{self.interview.id}/evaluation/review/"
        resp = self.client.patch(url, {"final_decision": "hire", "recruiter_notes": "a" * 5001}, format="json", **self.r1_auth)
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["error_code"], "NOTES_TOO_LONG")

    def test_other_recruiter_cannot_submit_review(self):
        """Recruiter 2 cannot submit review for Recruiter 1's interview."""
        url = f"/api/v1/interviews/{self.interview.id}/evaluation/review/"
        resp = self.client.patch(url, {"final_decision": "hire"}, format="json", **self.r2_auth)
        self.assertEqual(resp.status_code, 404)

    def test_review_rejected_if_interview_not_completed(self):
        """Cannot submit review on in-progress or draft interview."""
        self.interview.status = Interview.STATUS_IN_PROGRESS
        self.interview.save(update_fields=['status'])

        url = f"/api/v1/interviews/{self.interview.id}/evaluation/review/"
        resp = self.client.patch(url, {"final_decision": "hire"}, format="json", **self.r1_auth)
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["error_code"], "INTERVIEW_NOT_COMPLETED")

    def test_review_rejected_if_evaluation_is_processing(self):
        """Cannot submit review while evaluation is still processing."""
        self.evaluation.evaluation_status = EvaluationResult.EVAL_STATUS_PROCESSING
        self.evaluation.save(update_fields=['evaluation_status'])

        url = f"/api/v1/interviews/{self.interview.id}/evaluation/review/"
        resp = self.client.patch(url, {"final_decision": "hire"}, format="json", **self.r1_auth)
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["error_code"], "EVALUATION_PROCESSING")

    # --- 2. Manual Retry Endpoint Tests ---

    @patch("evaluations.tasks.generate_evaluation_task.delay")
    def test_manual_retry_enqueued_successfully(self, mock_delay):
        """Failed or missing evaluation can be retried by owning recruiter."""
        self.evaluation.evaluation_status = EvaluationResult.EVAL_STATUS_FAILED
        self.evaluation.save(update_fields=['evaluation_status'])

        url = f"/api/v1/interviews/{self.interview.id}/evaluation/retry/"
        resp = self.client.post(url, **self.r1_auth)
        self.assertEqual(resp.status_code, 202)
        self.assertEqual(resp.json()["evaluation_status"], "processing")
        mock_delay.assert_called_once_with(str(self.interview.id))

    def test_manual_retry_rejected_if_already_reviewed(self):
        """A reviewed evaluation cannot be regenerated via retry."""
        self.evaluation.review_status = EvaluationResult.STATUS_REVIEWED
        self.evaluation.save(update_fields=['review_status'])

        url = f"/api/v1/interviews/{self.interview.id}/evaluation/retry/"
        resp = self.client.post(url, **self.r1_auth)
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["error_code"], "ALREADY_REVIEWED")

    def test_manual_retry_rejected_if_already_completed(self):
        """A completed evaluation cannot be regenerated via standard retry."""
        self.evaluation.evaluation_status = EvaluationResult.EVAL_STATUS_COMPLETED
        self.evaluation.save(update_fields=['evaluation_status'])

        url = f"/api/v1/interviews/{self.interview.id}/evaluation/retry/"
        resp = self.client.post(url, **self.r1_auth)
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["error_code"], "ALREADY_COMPLETED")

    def test_other_recruiter_cannot_trigger_retry(self):
        """Another recruiter cannot trigger retry on another recruiter's interview."""
        url = f"/api/v1/interviews/{self.interview.id}/evaluation/retry/"
        resp = self.client.post(url, **self.r2_auth)
        self.assertEqual(resp.status_code, 404)

    # --- 3. Phase 10.2.1 Celery Broker Failure Recovery Tests ---

    @patch("evaluations.tasks.generate_evaluation_task.delay")
    def test_broker_failure_returns_503_and_reverts_state_to_retryable(self, mock_delay):
        """When broker fails on dispatch, status reverts to failed and retry remains possible."""
        mock_delay.side_effect = Exception("Redis connection refused on redis://localhost:6379")

        self.evaluation.evaluation_status = EvaluationResult.EVAL_STATUS_FAILED
        self.evaluation.error_message = "Previous timeout"
        self.evaluation.save(update_fields=['evaluation_status', 'error_message'])

        url = f"/api/v1/interviews/{self.interview.id}/evaluation/retry/"
        resp = self.client.post(url, **self.r1_auth)
        self.assertEqual(resp.status_code, 503)
        self.assertEqual(resp.json()["error_code"], "BROKER_UNAVAILABLE")
        self.assertNotIn("localhost:6379", resp.json()["detail"])

        # Check database: must NOT be stuck in processing!
        self.evaluation.refresh_from_db()
        self.assertEqual(self.evaluation.evaluation_status, EvaluationResult.EVAL_STATUS_FAILED)

        # Subsequent retry should succeed once broker comes back
        mock_delay.side_effect = None
        resp2 = self.client.post(url, **self.r1_auth)
        self.assertEqual(resp2.status_code, 202)
        self.assertEqual(resp2.json()["evaluation_status"], "processing")


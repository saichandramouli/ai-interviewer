import json
from unittest.mock import patch, MagicMock
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import User
from candidates.models import Candidate
from jobs.models import Job
from interviews.models import Interview, InterviewQuestion, TranscriptEntry
from evaluations.models import EvaluationResult
from evaluations.services.evaluation_service import (
    EvaluationService,
    EvaluationAPIError,
    EvaluationValidationError,
)
from evaluations.tasks import generate_evaluation_task
from interviews.services.orchestrator import InterviewOrchestrationService


class Phase10_1_EvaluationEngineTests(TestCase):
    def setUp(self):
        self.client = APIClient()

        # Create Recruiters
        self.recruiter1 = User.objects.create_user(
            email="recruiter1_eval@example.com",
            password="Password123!",
            first_name="Recruiter",
            last_name="One",
        )
        self.recruiter2 = User.objects.create_user(
            email="recruiter2_eval@example.com",
            password="Password123!",
            first_name="Recruiter",
            last_name="Two",
        )

        # JWT Token for Recruiter 1
        resp = self.client.post("/api/v1/auth/token/", {
            "email": "recruiter1_eval@example.com",
            "password": "Password123!",
        })
        self.r1_token = resp.json()["access"]
        self.r1_auth = {"HTTP_AUTHORIZATION": f"Bearer {self.r1_token}"}

        # Create Candidate & Job
        self.candidate = Candidate.objects.create(
            created_by=self.recruiter1,
            full_name="Alex Mercer",
            email="alex@example.com",
            consent_status=Candidate.CONSENT_GRANTED,
            extracted_resume_text="Senior Python Backend Developer with 5 years experience in Django and PostgreSQL."
        )
        self.job = Job.objects.create(
            created_by=self.recruiter1,
            title="Senior Python Engineer",
            description="Build scalable microservices and APIs with Django and Celery.",
            required_skills=["Python", "Django", "PostgreSQL", "Celery"],
            experience_requirements="5+ years backend development",
        )

        # Create Interview
        self.interview = Interview.objects.create(
            created_by=self.recruiter1,
            candidate=self.candidate,
            job=self.job,
            status=Interview.STATUS_IN_PROGRESS,
            started_at=timezone.now(),
            plan_data={"introduction": "Welcome to the interview.", "closing_statement": "Thank you for your time."},
        )

        # Create Questions
        self.q1 = InterviewQuestion.objects.create(
            interview=self.interview,
            sequence_number=1,
            competency="Python & Django",
            question_text="Explain how Django database transactions work.",
            expected_evidence="Mentions atomic blocks, commit hooks, and ACID properties.",
        )
        self.q2 = InterviewQuestion.objects.create(
            interview=self.interview,
            sequence_number=2,
            competency="System Design & Celery",
            question_text="How do you ensure idempotency in background tasks?",
            expected_evidence="Mentions unique task keys, database locks, and state checks.",
        )

        # Create Spoken Transcripts
        TranscriptEntry.objects.create(
            interview=self.interview,
            sequence_number=1,
            speaker=TranscriptEntry.SPEAKER_AI,
            text="Explain how Django database transactions work.",
            timestamp=timezone.now(),
        )
        TranscriptEntry.objects.create(
            interview=self.interview,
            sequence_number=2,
            speaker=TranscriptEntry.SPEAKER_CANDIDATE,
            text="In Django, transaction.atomic wraps database queries in a transaction. You can use on_commit hooks for safe asynchronous dispatch.",
            timestamp=timezone.now(),
        )
        TranscriptEntry.objects.create(
            interview=self.interview,
            sequence_number=3,
            speaker=TranscriptEntry.SPEAKER_AI,
            text="How do you ensure idempotency in background tasks?",
            timestamp=timezone.now(),
        )
        TranscriptEntry.objects.create(
            interview=self.interview,
            sequence_number=4,
            speaker=TranscriptEntry.SPEAKER_CANDIDATE,
            text="I use database select_for_update or unique constraints to ensure only one worker processes a job.",
            timestamp=timezone.now(),
        )

    # --- 1. Service Tests ---

    @patch("evaluations.services.evaluation_service.requests.Session.post")
    def test_evaluation_service_success(self, mock_post):
        """Valid Nemotron response is parsed, validated, and persisted properly."""
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "choices": [{
                    "message": {
                        "content": json.dumps({
                            "overall_score": 88.0,
                            "competency_scores": {
                                "Python & Django": 90.0,
                                "System Design & Celery": 86.0
                            },
                            "competency_details": [
                                {
                                    "competency": "Python & Django",
                                    "score": 90.0,
                                    "weight": 0.5,
                                    "strengths": ["Clear explanation of transaction.atomic and on_commit"],
                                    "improvement_areas": [],
                                    "evidence_sufficient": True
                                },
                                {
                                    "competency": "System Design & Celery",
                                    "score": 86.0,
                                    "weight": 0.5,
                                    "strengths": ["Understands row-level locking with select_for_update"],
                                    "improvement_areas": [],
                                    "evidence_sufficient": True
                                }
                            ],
                            "strengths": ["Strong conceptual grasp of transactional consistency."],
                            "improvement_areas": ["Could provide distributed caching examples."],
                            "evidence_summary": "Candidate demonstrated strong backend skills with concrete answers.",
                            "question_evaluations": [],
                            "evaluation_completeness": "complete",
                            "missing_evidence": []
                        })
                    }
                }]
            }
        )

        self.interview.status = Interview.STATUS_COMPLETED
        self.interview.save(update_fields=['status'])

        service = EvaluationService(api_key="nvapi-mock-test-key")
        result = service.evaluate_interview(self.interview)

        self.assertIsNotNone(result)
        self.assertEqual(result.overall_score, 88.0)
        self.assertEqual(result.evaluation_status, EvaluationResult.EVAL_STATUS_COMPLETED)
        self.assertIn("Python & Django", result.competency_scores)
        self.assertTrue(len(result.strengths) > 0)

    def test_evaluation_service_empty_transcript_insufficient_data(self):
        """If candidate did not speak, evaluation is marked as insufficient_data without fabrication."""
        # Create completed interview without candidate turns
        interview_silent = Interview.objects.create(
            created_by=self.recruiter1,
            candidate=self.candidate,
            job=self.job,
            status=Interview.STATUS_COMPLETED,
        )

        service = EvaluationService(api_key="nvapi-mock-test-key")
        result = service.evaluate_interview(interview_silent)

        self.assertEqual(result.evaluation_status, EvaluationResult.EVAL_STATUS_INSUFFICIENT)
        self.assertIsNone(result.overall_score)
        self.assertIn("no audible or transcribed answers", result.improvement_areas[0])

    def test_evaluation_service_ineligible_status_rejected(self):
        """In-progress or draft interviews cannot be evaluated."""
        self.interview.status = Interview.STATUS_IN_PROGRESS
        self.interview.save(update_fields=['status'])

        service = EvaluationService(api_key="nvapi-mock-test-key")
        with self.assertRaises(Exception):
            service.evaluate_interview(self.interview)

    # --- 2. Celery Task & Concurrency / Idempotency Tests ---

    @patch("evaluations.services.evaluation_service.EvaluationService.evaluate_interview")
    def test_generate_evaluation_task_success(self, mock_evaluate):
        """Celery task executes evaluate_interview and completes."""
        self.interview.status = Interview.STATUS_COMPLETED
        self.interview.save(update_fields=['status'])

        mock_evaluate.return_value = EvaluationResult(
            interview=self.interview,
            overall_score=82.0,
            evaluation_status=EvaluationResult.EVAL_STATUS_COMPLETED
        )

        generate_evaluation_task(str(self.interview.id))
        mock_evaluate.assert_called_once()

    @patch("evaluations.services.evaluation_service.EvaluationService.evaluate_interview")
    def test_generate_evaluation_task_idempotency_skip_completed(self, mock_evaluate):
        """If an evaluation is already completed, repeated task does not re-run evaluation."""
        self.interview.status = Interview.STATUS_COMPLETED
        self.interview.save(update_fields=['status'])

        EvaluationResult.objects.create(
            interview=self.interview,
            overall_score=85.0,
            evaluation_status=EvaluationResult.EVAL_STATUS_COMPLETED,
            review_status=EvaluationResult.STATUS_PENDING,
        )

        generate_evaluation_task(str(self.interview.id))
        mock_evaluate.assert_not_called()

    @patch("evaluations.services.evaluation_service.EvaluationService.evaluate_interview")
    def test_generate_evaluation_task_skip_reviewed_evaluation(self, mock_evaluate):
        """If an evaluation has been reviewed by recruiter, it is never overwritten."""
        self.interview.status = Interview.STATUS_COMPLETED
        self.interview.save(update_fields=['status'])

        EvaluationResult.objects.create(
            interview=self.interview,
            overall_score=85.0,
            evaluation_status=EvaluationResult.EVAL_STATUS_COMPLETED,
            review_status=EvaluationResult.STATUS_REVIEWED,
        )

        generate_evaluation_task(str(self.interview.id))
        mock_evaluate.assert_not_called()

    # --- 3. Interview Completion Auto-Trigger Tests ---

    @patch("evaluations.tasks.generate_evaluation_task.delay")
    def test_orchestrator_conclude_triggers_evaluation_task(self, mock_delay):
        """Conclude interview automatically schedules generate_evaluation_task on transaction commit."""
        orchestrator = InterviewOrchestrationService(self.interview)
        with self.captureOnCommitCallbacks(execute=True):
            orchestrator.conclude_interview(reason="Interview questions finished.")

        self.assertEqual(self.interview.status, Interview.STATUS_COMPLETED)
        mock_delay.assert_called_once_with(str(self.interview.id))

    @patch("evaluations.tasks.generate_evaluation_task.delay")
    def test_cancel_interview_never_triggers_evaluation(self, mock_delay):
        """Cancelled interviews must never schedule an evaluation task."""
        orchestrator = InterviewOrchestrationService(self.interview)
        with self.captureOnCommitCallbacks(execute=True):
            orchestrator.cancel_interview(reason="Candidate cancelled.")

        self.assertEqual(self.interview.status, Interview.STATUS_CANCELLED)
        mock_delay.assert_not_called()

    # --- 4. Recruiter API & Tenant Security Tests ---

    def test_recruiter_can_retrieve_evaluation_status_and_result(self):
        """Owning recruiter can retrieve evaluation via /api/v1/interviews/{id}/evaluation/."""
        self.interview.status = Interview.STATUS_COMPLETED
        self.interview.save(update_fields=['status'])

        EvaluationResult.objects.create(
            interview=self.interview,
            overall_score=87.5,
            competency_scores={"Python": 90.0},
            strengths=["Solid coding fundamentals"],
            improvement_areas=["None"],
            evidence_summary="Strong candidate.",
            evaluation_status=EvaluationResult.EVAL_STATUS_COMPLETED,
        )

        url = f"/api/v1/interviews/{self.interview.id}/evaluation/"
        resp = self.client.get(url, **self.r1_auth)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["overall_score"], 87.5)
        self.assertEqual(resp.json()["evaluation_status"], "completed")

    def test_other_recruiter_cannot_access_evaluation(self):
        """Another recruiter cannot view evaluation results for an interview they do not own."""
        resp2 = self.client.post("/api/v1/auth/token/", {
            "email": "recruiter2_eval@example.com",
            "password": "Password123!",
        })
        r2_auth = {"HTTP_AUTHORIZATION": f"Bearer {resp2.json()['access']}"}

        url = f"/api/v1/interviews/{self.interview.id}/evaluation/"
        resp = self.client.get(url, **r2_auth)
        self.assertEqual(resp.status_code, 404)

    def test_public_candidate_endpoints_cannot_access_evaluation(self):
        """Candidate session endpoints do not expose evaluation results."""
        url = f"/api/v1/candidate/session/?token=some-token"
        resp = self.client.get(url)
        # Should be 401 or not contain evaluation details
        self.assertNotIn("overall_score", resp.content.decode())
        self.assertNotIn("competency_scores", resp.content.decode())

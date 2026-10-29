import io
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
import docx

from operations.models import AsyncOperation
from candidates.models import Candidate
from jobs.models import Job
from interviews.models import Interview, InterviewQuestion
from candidates.tasks import extract_resume_task
from interviews.tasks import generate_plan_task
from interviews.services.question_generator import (
    GeneratedInterviewPlan,
    GeneratedQuestion,
    OpenAIServiceError,
    ConfigurationError,
)

User = get_user_model()


class Phase5AsyncProcessingTestSuite(TestCase):
    def setUp(self):
        self.recruiter1 = User.objects.create_user(
            email="recruiter_p5_1@example.com",
            password="Password123!",
        )
        self.recruiter2 = User.objects.create_user(
            email="recruiter_p5_2@example.com",
            password="Password123!",
        )

        # JWT Auth for recruiter 1
        t_url = reverse("token_obtain_pair")
        resp1 = self.client.post(
            t_url,
            {"email": "recruiter_p5_1@example.com", "password": "Password123!"},
            content_type="application/json",
        )
        self.r1_auth = {"HTTP_AUTHORIZATION": f"Bearer {resp1.json()['access']}"}

        # JWT Auth for recruiter 2
        resp2 = self.client.post(
            t_url,
            {"email": "recruiter_p5_2@example.com", "password": "Password123!"},
            content_type="application/json",
        )
        self.r2_auth = {"HTTP_AUTHORIZATION": f"Bearer {resp2.json()['access']}"}

        # Sample Candidate & Job
        doc = docx.Document()
        doc.add_paragraph("Expert in Django, PostgreSQL, and Celery asynchronous tasks.")
        stream = io.BytesIO()
        doc.save(stream)
        docx_bytes = stream.getvalue()

        self.candidate = Candidate.objects.create(
            full_name="Marcus Vance",
            email="marcus@example.com",
            resume=SimpleUploadedFile("marcus_resume.docx", docx_bytes),
            created_by=self.recruiter1,
        )
        self.job = Job.objects.create(
            title="Senior Platform Engineer",
            description="Build scalable distributed task processing systems.",
            required_skills=["Python", "Django", "Celery", "Redis"],
            created_by=self.recruiter1,
        )
        self.interview = Interview.objects.create(
            candidate=self.candidate,
            job=self.job,
            created_by=self.recruiter1,
            status=Interview.STATUS_DRAFT,
        )

    # 1. Extraction Task Tests
    def test_extract_resume_task_success(self):
        fingerprint = f"{self.candidate.resume.name}:{self.candidate.resume.size}"
        operation = AsyncOperation.objects.create(
            operation_type=AsyncOperation.TYPE_RESUME_EXTRACTION,
            status=AsyncOperation.STATUS_PENDING,
            created_by=self.recruiter1,
            candidate=self.candidate,
            target_fingerprint=fingerprint,
        )

        extract_resume_task(str(operation.id), str(self.candidate.id), fingerprint)

        operation.refresh_from_db()
        self.assertEqual(operation.status, AsyncOperation.STATUS_SUCCEEDED)
        self.assertIn("extracted successfully", operation.status_message)
        self.assertIsNotNone(operation.completed_at)

        self.candidate.refresh_from_db()
        self.assertIn("Expert in Django, PostgreSQL", self.candidate.extracted_resume_text)

    def test_extract_resume_task_stale_fingerprint_rejected(self):
        operation = AsyncOperation.objects.create(
            operation_type=AsyncOperation.TYPE_RESUME_EXTRACTION,
            status=AsyncOperation.STATUS_PENDING,
            created_by=self.recruiter1,
            candidate=self.candidate,
            target_fingerprint="old_file.docx:1234",
        )

        extract_resume_task(str(operation.id), str(self.candidate.id), "old_file.docx:1234")

        operation.refresh_from_db()
        self.assertEqual(operation.status, AsyncOperation.STATUS_FAILED)
        self.assertEqual(operation.error_code, "STALE_TASK_DETECTED")

    def test_extract_resume_task_corrupt_file_failure(self):
        # Replace with corrupt file
        self.candidate.resume = SimpleUploadedFile("corrupt.pdf", b"%PDF-1.4 corrupt content \x00\xff")
        self.candidate.save()
        fingerprint = f"{self.candidate.resume.name}:{self.candidate.resume.size}"

        operation = AsyncOperation.objects.create(
            operation_type=AsyncOperation.TYPE_RESUME_EXTRACTION,
            status=AsyncOperation.STATUS_PENDING,
            created_by=self.recruiter1,
            candidate=self.candidate,
            target_fingerprint=fingerprint,
        )

        extract_resume_task(str(operation.id), str(self.candidate.id), fingerprint)

        operation.refresh_from_db()
        self.assertEqual(operation.status, AsyncOperation.STATUS_FAILED)
        self.assertEqual(operation.error_code, "DOCUMENT_CORRUPTED")

    # 2. Plan Generation Task Tests
    @patch("interviews.tasks.generate_interview_plan")
    def test_generate_plan_task_success(self, mock_gen_plan):
        self.candidate.extracted_resume_text = "Experienced in Celery and Redis queuing."
        self.candidate.save()

        mock_plan = GeneratedInterviewPlan(
            introduction="Welcome Marcus to the interview.",
            closing_statement="Thank you Marcus.",
            total_estimated_minutes=25,
            questions=[
                GeneratedQuestion(
                    sequence_number=1,
                    question_text="How do you handle worker failure in Celery?",
                    category="technical",
                    competency="Distributed Systems",
                    expected_evidence="Mentions retry policies, dead letter queues, and ACK late.",
                    suggested_follow_up="What broker do you prefer?",
                    estimated_minutes=4,
                    max_score=10.0,
                )
            ],
        )
        mock_gen_plan.return_value = mock_plan

        operation = AsyncOperation.objects.create(
            operation_type=AsyncOperation.TYPE_PLAN_GENERATION,
            status=AsyncOperation.STATUS_PENDING,
            created_by=self.recruiter1,
            interview=self.interview,
            candidate=self.candidate,
        )

        generate_plan_task(str(operation.id), str(self.interview.id))

        operation.refresh_from_db()
        self.assertEqual(operation.status, AsyncOperation.STATUS_SUCCEEDED)
        self.assertIn("generated successfully", operation.status_message)

        self.interview.refresh_from_db()
        self.assertEqual(self.interview.questions.count(), 1)
        q = self.interview.questions.first()
        self.assertEqual(q.competency, "Distributed Systems")

    @patch("interviews.tasks.generate_interview_plan")
    def test_generate_plan_task_permanent_error_no_retry(self, mock_gen_plan):
        self.candidate.extracted_resume_text = "Some resume text."
        self.candidate.save()

        mock_gen_plan.side_effect = ConfigurationError("API Key missing.")

        operation = AsyncOperation.objects.create(
            operation_type=AsyncOperation.TYPE_PLAN_GENERATION,
            status=AsyncOperation.STATUS_PENDING,
            created_by=self.recruiter1,
            interview=self.interview,
            candidate=self.candidate,
        )

        generate_plan_task(str(operation.id), str(self.interview.id))

        operation.refresh_from_db()
        self.assertEqual(operation.status, AsyncOperation.STATUS_FAILED)
        self.assertEqual(operation.error_code, "AI_CONFIGURATION_MISSING")

    # 3. Operations API Endpoint & Ownership Isolation Tests
    def test_operations_endpoint_and_recruiter_isolation(self):
        op = AsyncOperation.objects.create(
            operation_type=AsyncOperation.TYPE_RESUME_EXTRACTION,
            status=AsyncOperation.STATUS_SUCCEEDED,
            created_by=self.recruiter1,
            candidate=self.candidate,
            status_message="Extracted 500 characters.",
        )

        url = reverse("operation-detail", kwargs={"pk": str(op.id)})

        # Recruiter 1 can view their operation
        resp1 = self.client.get(url, **self.r1_auth)
        self.assertEqual(resp1.status_code, 200)
        data = resp1.json()
        self.assertEqual(data["id"], str(op.id))
        self.assertEqual(data["status"], "succeeded")
        self.assertEqual(data["operation_type"], "resume_extraction")
        # Ensure no sensitive internals exposed
        self.assertNotIn("target_fingerprint", data)
        self.assertNotIn("stack_trace", data)

        # Recruiter 2 cannot view recruiter 1's operation (404)
        resp2 = self.client.get(url, **self.r2_auth)
        self.assertEqual(resp2.status_code, 404)

    def test_operations_unauthenticated_rejected(self):
        op = AsyncOperation.objects.create(
            operation_type=AsyncOperation.TYPE_RESUME_EXTRACTION,
            status=AsyncOperation.STATUS_PENDING,
            created_by=self.recruiter1,
        )
        url = reverse("operation-detail", kwargs={"pk": str(op.id)})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 401)

    # 4. Duplicate Active Operation Prevention in Views
    def test_duplicate_active_extraction_rejected(self):
        # Create an active pending extraction
        AsyncOperation.objects.create(
            operation_type=AsyncOperation.TYPE_RESUME_EXTRACTION,
            status=AsyncOperation.STATUS_RUNNING,
            created_by=self.recruiter1,
            candidate=self.candidate,
        )

        url = reverse("candidate-extract-resume", kwargs={"pk": str(self.candidate.id)})
        resp = self.client.post(url, **self.r1_auth)
        self.assertEqual(resp.status_code, 409)
        self.assertIn("already in progress", resp.json()["detail"])

    def test_duplicate_active_plan_generation_rejected(self):
        self.candidate.extracted_resume_text = "Extracted resume."
        self.candidate.save()

        # Create active pending plan generation
        AsyncOperation.objects.create(
            operation_type=AsyncOperation.TYPE_PLAN_GENERATION,
            status=AsyncOperation.STATUS_PENDING,
            created_by=self.recruiter1,
            interview=self.interview,
            candidate=self.candidate,
        )

        url = reverse("interview-generate-plan", kwargs={"pk": str(self.interview.id)})
        resp = self.client.post(url, **self.r1_auth)
        self.assertEqual(resp.status_code, 409)
        self.assertIn("already in progress", resp.json()["detail"])

import json
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from candidates.models import Candidate
from jobs.models import Job
from interviews.models import (
    Interview,
    InterviewQuestion,
    TranscriptEntry,
    InterviewStatusTransitionError,
)
from evaluations.models import EvaluationResult

User = get_user_model()


class Phase3CoreTestSuite(TestCase):
    def setUp(self):
        self.recruiter1 = User.objects.create_user(
            email="recruiter1@example.com",
            password="Password123!",
        )
        self.recruiter2 = User.objects.create_user(
            email="recruiter2@example.com",
            password="Password123!",
        )

        # Obtain JWT tokens for recruiter1
        token_url = reverse("token_obtain_pair")
        resp = self.client.post(
            token_url,
            {"email": "recruiter1@example.com", "password": "Password123!"},
            content_type="application/json",
        )
        self.r1_access = resp.json()["access"]
        self.r1_refresh = resp.json()["refresh"]
        self.r1_auth_header = {"HTTP_AUTHORIZATION": f"Bearer {self.r1_access}"}

        # Obtain JWT tokens for recruiter2
        resp2 = self.client.post(
            token_url,
            {"email": "recruiter2@example.com", "password": "Password123!"},
            content_type="application/json",
        )
        self.r2_access = resp2.json()["access"]
        self.r2_auth_header = {"HTTP_AUTHORIZATION": f"Bearer {self.r2_access}"}

    # 1. Authentication Tests
    def test_successful_authentication(self):
        url = reverse("token_obtain_pair")
        resp = self.client.post(
            url,
            {"email": "recruiter1@example.com", "password": "Password123!"},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn("access", resp.json())
        self.assertIn("refresh", resp.json())

    def test_invalid_credentials_rejected(self):
        url = reverse("token_obtain_pair")
        resp = self.client.post(
            url,
            {"email": "recruiter1@example.com", "password": "WrongPassword"},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 401)

    def test_inactive_user_cannot_authenticate(self):
        self.recruiter1.is_active = False
        self.recruiter1.save()
        url = reverse("token_obtain_pair")
        resp = self.client.post(
            url,
            {"email": "recruiter1@example.com", "password": "Password123!"},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 401)

    def test_token_refresh_and_verify(self):
        refresh_url = reverse("token_refresh")
        resp = self.client.post(
            refresh_url,
            {"refresh": self.r1_refresh},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        new_access = resp.json()["access"]
        self.assertIsNotNone(new_access)

        verify_url = reverse("token_verify")
        resp_v = self.client.post(
            verify_url,
            {"token": new_access},
            content_type="application/json",
        )
        self.assertEqual(resp_v.status_code, 200)

    def test_unauthenticated_requests_rejected(self):
        url = reverse("candidate-list")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 401)

    # 2. Candidate & Job CRUD + Validation
    def test_candidate_crud_and_isolation(self):
        # Create candidate as recruiter1
        c_url = reverse("candidate-list")
        data = {
            "full_name": "Alice Doe",
            "email": "alice@example.com",
            "phone_number": "+1234567890",
            "consent_status": "pending",
        }
        resp = self.client.post(c_url, data, content_type="application/json", **self.r1_auth_header)
        self.assertEqual(resp.status_code, 201)
        candidate_id = resp.json()["id"]

        # Recruiter1 can view
        detail_url = reverse("candidate-detail", kwargs={"pk": candidate_id})
        resp = self.client.get(detail_url, **self.r1_auth_header)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["full_name"], "Alice Doe")

        # Recruiter2 cannot view (404 isolation)
        resp2 = self.client.get(detail_url, **self.r2_auth_header)
        self.assertEqual(resp2.status_code, 404)

        # Update candidate
        resp_patch = self.client.patch(
            detail_url,
            {"consent_status": "granted", "consent_method": "verbal_confirmation"},
            content_type="application/json",
            **self.r1_auth_header,
        )
        self.assertEqual(resp_patch.status_code, 200)
        self.assertEqual(resp_patch.json()["consent_status"], "granted")

    def test_resume_extension_and_size_validation(self):
        c = Candidate(
            full_name="Bob Test",
            email="bob@example.com",
            created_by=self.recruiter1,
        )
        # Invalid extension
        invalid_file = SimpleUploadedFile("resume.exe", b"binary content")
        c.resume = invalid_file
        with self.assertRaises(ValidationError):
            c.full_clean()

        # Valid extension
        valid_file = SimpleUploadedFile("resume.pdf", b"%PDF-1.4 test resume content")
        c.resume = valid_file
        c.full_clean()  # Should not raise

    def test_job_crud_and_isolation(self):
        j_url = reverse("job-list")
        data = {
            "title": "Senior Python Engineer",
            "description": "Develop high-scale backend services",
            "required_skills": ["Python", "Django", "PostgreSQL"],
        }
        resp = self.client.post(j_url, data, content_type="application/json", **self.r1_auth_header)
        self.assertEqual(resp.status_code, 201)
        job_id = resp.json()["id"]

        # Detail accessible by recruiter1
        detail_url = reverse("job-detail", kwargs={"pk": job_id})
        resp1 = self.client.get(detail_url, **self.r1_auth_header)
        self.assertEqual(resp1.status_code, 200)

        # Isolated from recruiter2
        resp2 = self.client.get(detail_url, **self.r2_auth_header)
        self.assertEqual(resp2.status_code, 404)

    # 3. Cross-Recruiter Assignment & Interview Creation
    def test_cross_recruiter_assignment_rejected(self):
        # Candidate and Job created by Recruiter 2
        r2_candidate = Candidate.objects.create(
            full_name="Charlie",
            email="charlie@example.com",
            created_by=self.recruiter2,
        )
        r2_job = Job.objects.create(
            title="Frontend Dev",
            description="React",
            created_by=self.recruiter2,
        )

        # Recruiter1 creates their own candidate & job
        r1_candidate = Candidate.objects.create(
            full_name="David",
            email="david@example.com",
            created_by=self.recruiter1,
        )
        r1_job = Job.objects.create(
            title="DevOps",
            description="Cloud",
            created_by=self.recruiter1,
        )

        i_url = reverse("interview-list")

        # Recruiter1 tries to use Recruiter2's candidate -> Rejected 400
        bad_payload1 = {
            "candidate": str(r2_candidate.id),
            "job": str(r1_job.id),
        }
        resp1 = self.client.post(i_url, bad_payload1, content_type="application/json", **self.r1_auth_header)
        self.assertEqual(resp1.status_code, 400)
        self.assertIn("candidate", resp1.json())

        # Recruiter1 tries to use Recruiter2's job -> Rejected 400
        bad_payload2 = {
            "candidate": str(r1_candidate.id),
            "job": str(r2_job.id),
        }
        resp2 = self.client.post(i_url, bad_payload2, content_type="application/json", **self.r1_auth_header)
        self.assertEqual(resp2.status_code, 400)
        self.assertIn("job", resp2.json())

    # 4. Status Transition Enforcement
    def test_interview_status_transitions(self):
        c = Candidate.objects.create(
            full_name="Eva",
            email="eva@example.com",
            created_by=self.recruiter1,
        )
        j = Job.objects.create(
            title="AI Researcher",
            description="LLM",
            created_by=self.recruiter1,
        )
        interview = Interview.objects.create(
            candidate=c,
            job=j,
            created_by=self.recruiter1,
            status=Interview.STATUS_DRAFT,
        )

        # Valid transition: draft -> scheduled
        interview.transition_to(Interview.STATUS_SCHEDULED)
        self.assertEqual(interview.status, Interview.STATUS_SCHEDULED)

        # Valid transition: scheduled -> calling
        interview.transition_to(Interview.STATUS_CALLING)
        self.assertEqual(interview.status, Interview.STATUS_CALLING)

        # Invalid transition: calling -> completed directly without in_progress
        with self.assertRaises(InterviewStatusTransitionError):
            interview.transition_to(Interview.STATUS_COMPLETED)

        # API status transition validation
        detail_url = reverse("interview-detail", kwargs={"pk": str(interview.id)})
        bad_api_patch = self.client.patch(
            detail_url,
            {"status": Interview.STATUS_COMPLETED},
            content_type="application/json",
            **self.r1_auth_header,
        )
        self.assertEqual(bad_api_patch.status_code, 400)
        self.assertIn("status", bad_api_patch.json())

    # 5. Question & Transcript Sequence Constraints
    def test_question_and_transcript_sequence_uniqueness(self):
        c = Candidate.objects.create(
            full_name="Frank",
            email="frank@example.com",
            created_by=self.recruiter1,
        )
        j = Job.objects.create(
            title="Backend Dev",
            description="Django",
            created_by=self.recruiter1,
        )
        interview = Interview.objects.create(
            candidate=c,
            job=j,
            created_by=self.recruiter1,
        )

        from django.db import transaction

        # 1. Create first question with sequence 1
        InterviewQuestion.objects.create(
            interview=interview,
            sequence_number=1,
            question_text="Explain Django ORM.",
        )
        # Attempting duplicate sequence 1 raises IntegrityError
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                InterviewQuestion.objects.create(
                    interview=interview,
                    sequence_number=1,
                    question_text="Duplicate sequence.",
                )

        # 2. Create first transcript entry with sequence 1
        TranscriptEntry.objects.create(
            interview=interview,
            sequence_number=1,
            speaker=TranscriptEntry.SPEAKER_AI,
            text="Hello, let us begin.",
            timestamp=timezone.now(),
        )
        # Attempting duplicate transcript sequence 1 raises IntegrityError
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                TranscriptEntry.objects.create(
                    interview=interview,
                    sequence_number=1,
                    speaker=TranscriptEntry.SPEAKER_CANDIDATE,
                    text="Hi there.",
                    timestamp=timezone.now(),
                )

    # 6. Evaluation Relationship and Nested Endpoints
    def test_evaluation_and_nested_endpoints(self):
        c = Candidate.objects.create(
            full_name="Grace",
            email="grace@example.com",
            created_by=self.recruiter1,
        )
        j = Job.objects.create(
            title="Fullstack",
            description="DRF + React",
            created_by=self.recruiter1,
        )
        interview = Interview.objects.create(
            candidate=c,
            job=j,
            created_by=self.recruiter1,
        )

        InterviewQuestion.objects.create(
            interview=interview,
            sequence_number=1,
            question_text="Tell me about yourself.",
        )
        TranscriptEntry.objects.create(
            interview=interview,
            sequence_number=1,
            speaker=TranscriptEntry.SPEAKER_AI,
            text="Welcome Grace.",
            timestamp=timezone.now(),
        )
        EvaluationResult.objects.create(
            interview=interview,
            overall_score=85.5,
            competency_scores={"technical": 85, "communication": 86},
            strengths=["Clean architecture knowledge"],
            improvement_areas=["Deep cloud networking"],
            evidence_summary="Strong candidate overall.",
        )

        # Test nested questions endpoint
        q_url = reverse("interview-questions", kwargs={"pk": str(interview.id)})
        resp_q = self.client.get(q_url, **self.r1_auth_header)
        self.assertEqual(resp_q.status_code, 200)
        self.assertEqual(len(resp_q.json()), 1)

        # Test nested transcript endpoint
        t_url = reverse("interview-transcript", kwargs={"pk": str(interview.id)})
        resp_t = self.client.get(t_url, **self.r1_auth_header)
        self.assertEqual(resp_t.status_code, 200)
        self.assertEqual(len(resp_t.json()), 1)

        # Test nested evaluation endpoint
        e_url = reverse("interview-evaluation", kwargs={"pk": str(interview.id)})
        resp_e = self.client.get(e_url, **self.r1_auth_header)
        self.assertEqual(resp_e.status_code, 200)
        self.assertEqual(resp_e.json()["overall_score"], 85.5)

        # Recruiter 2 cannot view recruiter 1's nested data
        resp_e_r2 = self.client.get(e_url, **self.r2_auth_header)
        self.assertEqual(resp_e_r2.status_code, 404)

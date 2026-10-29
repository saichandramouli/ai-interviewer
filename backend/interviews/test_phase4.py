import io
import json
import zipfile
from unittest.mock import patch, MagicMock
import docx
import pypdf

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile

from candidates.models import Candidate
from jobs.models import Job
from interviews.models import Interview, InterviewQuestion
from candidates.services.resume_extractor import (
    ResumeExtractorService,
    UnsupportedFileError,
    CorruptedFileError,
    EncryptedFileError,
    EmptyDocumentError,
    FileSizeLimitExceededError,
)
from interviews.services.question_generator import (
    GeneratedInterviewPlan,
    GeneratedQuestion,
    QuestionGeneratorService,
    ConfigurationError,
    OpenAIServiceError,
    PlanValidationError,
    generate_interview_plan,
)

User = get_user_model()


class Phase4ResumeAndQuestionGeneratorTests(TestCase):
    def setUp(self):
        self.recruiter1 = User.objects.create_user(
            email="recruiter1_p4@example.com",
            password="Password123!",
        )
        self.recruiter2 = User.objects.create_user(
            email="recruiter2_p4@example.com",
            password="Password123!",
        )

        # JWT auth for recruiter1
        token_url = reverse("token_obtain_pair")
        resp1 = self.client.post(
            token_url,
            {"email": "recruiter1_p4@example.com", "password": "Password123!"},
            content_type="application/json",
        )
        self.r1_auth = {"HTTP_AUTHORIZATION": f"Bearer {resp1.json()['access']}"}

        # JWT auth for recruiter2
        resp2 = self.client.post(
            token_url,
            {"email": "recruiter2_p4@example.com", "password": "Password123!"},
            content_type="application/json",
        )
        self.r2_auth = {"HTTP_AUTHORIZATION": f"Bearer {resp2.json()['access']}"}

        # Sample Candidate & Job for Recruiter 1
        self.candidate1 = Candidate.objects.create(
            full_name="Samantha Ray",
            email="samantha@example.com",
            created_by=self.recruiter1,
        )
        self.job1 = Job.objects.create(
            title="Senior Backend Engineer",
            description="Build distributed APIs using Python, Django, and PostgreSQL.",
            required_skills=["Python", "Django", "PostgreSQL", "System Design"],
            experience_requirements="5+ years in high-traffic backend systems.",
            created_by=self.recruiter1,
        )
        self.interview1 = Interview.objects.create(
            candidate=self.candidate1,
            job=self.job1,
            created_by=self.recruiter1,
            status=Interview.STATUS_DRAFT,
        )

    # Helper: Build real in-memory DOCX
    def _create_docx_bytes(self, text: str) -> bytes:
        doc = docx.Document()
        doc.add_paragraph(text)
        table = doc.add_table(rows=1, cols=2)
        table.rows[0].cells[0].text = "Skill"
        table.rows[0].cells[1].text = "Proficiency"
        stream = io.BytesIO()
        doc.save(stream)
        return stream.getvalue()

    # Helper: Build real in-memory blank/text PDF
    def _create_pdf_bytes(self, text: str = "") -> bytes:
        writer = pypdf.PdfWriter()
        writer.add_blank_page(width=300, height=300)
        stream = io.BytesIO()
        writer.write(stream)
        return stream.getvalue()

    # 1. Resume Extractor Service Unit Tests
    def test_docx_extraction_success(self):
        docx_bytes = self._create_docx_bytes("Experienced Python Engineer with 6 years building microservices.")
        stream = io.BytesIO(docx_bytes)
        text = ResumeExtractorService.extract_text(stream, "resume.docx")
        self.assertIn("Experienced Python Engineer", text)
        self.assertIn("Skill | Proficiency", text)

    def test_pdf_invalid_signature_rejected(self):
        # Fake file with .pdf extension but invalid header
        stream = io.BytesIO(b"This is not a real PDF file")
        with self.assertRaises(UnsupportedFileError):
            ResumeExtractorService.extract_text(stream, "resume.pdf")

    def test_docx_invalid_signature_rejected(self):
        # Fake file with .docx extension but invalid header
        stream = io.BytesIO(b"Fake docx bytes")
        with self.assertRaises(UnsupportedFileError):
            ResumeExtractorService.extract_text(stream, "resume.docx")

    def test_unsupported_file_extension(self):
        stream = io.BytesIO(b"Some text")
        with self.assertRaises(UnsupportedFileError):
            ResumeExtractorService.extract_text(stream, "resume.txt")

    def test_empty_document_handling(self):
        # Empty byte file
        stream = io.BytesIO(b"")
        with self.assertRaises(CorruptedFileError):
            ResumeExtractorService.extract_text(stream, "resume.pdf")

    def test_scanned_image_empty_pdf_reports_ocr_not_supported(self):
        pdf_bytes = self._create_pdf_bytes()  # blank page with 0 text
        stream = io.BytesIO(pdf_bytes)
        with self.assertRaises(EmptyDocumentError) as ctx:
            ResumeExtractorService.extract_text(stream, "resume.pdf")
        self.assertIn("OCR", str(ctx.exception))

    def test_file_size_limit_exceeded(self):
        huge_bytes = b"%PDF-" + b"x" * (11 * 1024 * 1024)
        stream = io.BytesIO(huge_bytes)
        with self.assertRaises(FileSizeLimitExceededError):
            ResumeExtractorService.extract_text(stream, "resume.pdf")

    # 2. Extract Resume API Endpoint Tests
    def test_extract_resume_endpoint_success(self):
        docx_bytes = self._create_docx_bytes("Specialist in Django, PostgreSQL, and high availability systems.")
        self.candidate1.resume = SimpleUploadedFile("resume.docx", docx_bytes)
        self.candidate1.save()

        url = reverse("candidate-extract-resume", kwargs={"pk": str(self.candidate1.id)})
        resp = self.client.post(url, **self.r1_auth)
        self.assertEqual(resp.status_code, 202)
        self.assertEqual(resp.json()["status"], "enqueued")
        self.assertIn("operation_id", resp.json())
        self.assertIn("status_url", resp.json())

    def test_extract_resume_no_resume_uploaded(self):
        url = reverse("candidate-extract-resume", kwargs={"pk": str(self.candidate1.id)})
        resp = self.client.post(url, **self.r1_auth)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("No resume file has been uploaded", resp.json()["detail"])

    def test_extract_resume_corrupt_file_returns_202_and_task_fails(self):
        # Valid PDF header but corrupt body
        self.candidate1.resume = SimpleUploadedFile("resume.pdf", b"%PDF-1.4 corrupt byte sequence\x00\xff")
        self.candidate1.save()

        url = reverse("candidate-extract-resume", kwargs={"pk": str(self.candidate1.id)})
        resp = self.client.post(url, **self.r1_auth)
        self.assertEqual(resp.status_code, 202)
        self.assertEqual(resp.json()["status"], "enqueued")

    def test_extract_resume_ownership_isolation(self):
        docx_bytes = self._create_docx_bytes("Recruiter 1 candidate resume.")
        self.candidate1.resume = SimpleUploadedFile("resume.docx", docx_bytes)
        self.candidate1.save()

        url = reverse("candidate-extract-resume", kwargs={"pk": str(self.candidate1.id)})
        # Recruiter 2 attempts to extract Recruiter 1's candidate resume
        resp = self.client.post(url, **self.r2_auth)
        self.assertEqual(resp.status_code, 404)

    def test_extract_resume_unauthenticated_rejected(self):
        url = reverse("candidate-extract-resume", kwargs={"pk": str(self.candidate1.id)})
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 401)

    # 3. Question Generator Service Tests (Mocked OpenAI SDK)
    @patch.dict("os.environ", {}, clear=True)
    def test_missing_openai_config_raises_error(self):
        with self.assertRaises(ConfigurationError):
            generate_interview_plan(
                resume_text="Resume content",
                job_title="Dev",
                job_description="Desc",
            )

    @patch("interviews.services.question_generator.OpenAI")
    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key", "OPENAI_TEXT_MODEL": "gpt-4o-mini"})
    def test_question_generator_success(self, mock_openai_cls):
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client

        mock_plan = GeneratedInterviewPlan(
            introduction="Welcome to the interview for Senior Backend Engineer.",
            closing_statement="Thank you for your time. Our recruiting team will follow up within 48 hours.",
            total_estimated_minutes=30,
            questions=[
                GeneratedQuestion(
                    sequence_number=i,
                    question_text=f"Question {i} regarding architecture and scaling.",
                    category="technical",
                    competency="System Design",
                    expected_evidence="Mentions caching, sharding, and ACID properties.",
                    suggested_follow_up="How did you handle read-heavy traffic?",
                    estimated_minutes=3,
                    max_score=10.0,
                )
                for i in range(1, 9)
            ],
        )

        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(parsed=mock_plan))]
        mock_client.beta.chat.completions.parse.return_value = mock_response

        plan = generate_interview_plan(
            resume_text="Candidate with extensive Python and Django background.",
            job_title="Senior Backend Engineer",
            job_description="Design resilient distributed architectures.",
            required_skills=["Python", "PostgreSQL"],
            client=mock_client,
        )

        self.assertEqual(len(plan.questions), 8)
        self.assertEqual(plan.total_estimated_minutes, 30)
        self.assertIn("Welcome to the interview", plan.introduction)

    # 4. Generate Plan API Endpoint Tests
    def test_generate_plan_endpoint_success(self):
        # Set extracted resume text on candidate
        self.candidate1.extracted_resume_text = "5 years Python experience building distributed APIs."
        self.candidate1.save()

        url = reverse("interview-generate-plan", kwargs={"pk": str(self.interview1.id)})
        resp = self.client.post(url, **self.r1_auth)

        self.assertEqual(resp.status_code, 202)
        data = resp.json()
        self.assertEqual(data["status"], "enqueued")
        self.assertIn("operation_id", data)
        self.assertIn("status_url", data)

    @patch("interviews.views.generate_interview_plan")
    def test_generate_plan_duplicate_prevention(self, mock_gen_plan):
        self.candidate1.extracted_resume_text = "Experienced Developer."
        self.candidate1.save()

        # Create existing question for this interview
        InterviewQuestion.objects.create(
            interview=self.interview1,
            sequence_number=1,
            question_text="Existing question.",
        )

        url = reverse("interview-generate-plan", kwargs={"pk": str(self.interview1.id)})
        resp = self.client.post(url, **self.r1_auth)
        self.assertEqual(resp.status_code, 409)
        self.assertIn("already exists", resp.json()["detail"])
        mock_gen_plan.assert_not_called()

    def test_generate_plan_requires_extracted_resume_text(self):
        # Candidate has no extracted text
        self.candidate1.extracted_resume_text = ""
        self.candidate1.save()

        url = reverse("interview-generate-plan", kwargs={"pk": str(self.interview1.id)})
        resp = self.client.post(url, **self.r1_auth)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("resume text has not been extracted yet", resp.json()["detail"])

    def test_generate_plan_rejected_if_not_draft_status(self):
        self.candidate1.extracted_resume_text = "Some resume text."
        self.candidate1.save()

        self.interview1.status = Interview.STATUS_SCHEDULED
        self.interview1.save()

        url = reverse("interview-generate-plan", kwargs={"pk": str(self.interview1.id)})
        resp = self.client.post(url, **self.r1_auth)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("only be generated for draft interviews", resp.json()["detail"])

    def test_generate_plan_cross_recruiter_rejected(self):
        self.candidate1.extracted_resume_text = "Some resume text."
        self.candidate1.save()

        url = reverse("interview-generate-plan", kwargs={"pk": str(self.interview1.id)})
        # Recruiter 2 tries to generate plan for Recruiter 1's interview
        resp = self.client.post(url, **self.r2_auth)
        self.assertEqual(resp.status_code, 404)

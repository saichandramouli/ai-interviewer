import json
from unittest.mock import patch, MagicMock
from io import BytesIO
import requests
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from django.core.files.uploadedfile import SimpleUploadedFile

from candidates.models import Candidate
from jobs.models import Job
from interviews.models import (
    Interview,
    InterviewQuestion,
    TranscriptEntry,
    CandidateInterviewAccessToken,
)
from integrations.speech.base import STTResult, TTSResult

User = get_user_model()


class Phase83CandidateTestSuite(TestCase):
    def setUp(self):
        self.recruiter1 = User.objects.create_user(
            email="recruiter1@example.com",
            password="Password123!",
        )
        self.recruiter2 = User.objects.create_user(
            email="recruiter2@example.com",
            password="Password123!",
        )

        token_url = reverse("token_obtain_pair")
        resp = self.client.post(
            token_url,
            {"email": "recruiter1@example.com", "password": "Password123!"},
            content_type="application/json",
        )
        self.r1_auth = {"HTTP_AUTHORIZATION": f"Bearer {resp.json()['access']}"}

        # Candidate
        self.candidate = Candidate.objects.create(
            created_by=self.recruiter1,
            full_name="Priya Sharma",
            email="priya@example.com",
            phone_number="+919876543210",
            consent_status=Candidate.CONSENT_PENDING,
        )

        self.job = Job.objects.create(
            created_by=self.recruiter1,
            title="Senior Site Reliability Engineer",
            description="Manage Kubernetes clusters and high-availability systems.",
        )

        self.interview = Interview.objects.create(
            created_by=self.recruiter1,
            candidate=self.candidate,
            job=self.job,
            status=Interview.STATUS_DRAFT,
            duration_limit_seconds=1800,
            plan_data={
                "introduction": "Hello Priya, welcome to your SRE interview.",
                "closing_statement": "Thank you Priya, our team will review the interview.",
            },
        )

        self.q1 = InterviewQuestion.objects.create(
            interview=self.interview,
            sequence_number=1,
            question_text="How do you handle cascading failures across distributed microservices?",
            category="Reliability",
            competency="Incident Management",
        )
        self.q2 = InterviewQuestion.objects.create(
            interview=self.interview,
            sequence_number=2,
            question_text="Describe how you design circuit breakers for downstream dependencies.",
            category="Architecture",
            competency="Resilience",
        )

        # Generate candidate access token
        self.token_obj, self.raw_token = CandidateInterviewAccessToken.create_token(
            interview=self.interview,
            valid_hours=48,
        )

        self.candidate_auth = {"HTTP_AUTHORIZATION": f"Bearer {self.raw_token}"}
        self.valid_wav = (
            b"RIFF\x2c\x00\x00\x00WAVEfmt \x10\x00\x00\x00"
            b"\x01\x00\x01\x00\x80>\x00\x00\x00}\x00\x00"
            b"\x02\x00\x10\x00data\x08\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        )

    # 1. Candidate Link Generation & Token Validation
    def test_recruiter_can_generate_candidate_link(self):
        url = reverse("interview-generate-candidate-link", kwargs={"pk": str(self.interview.id)})
        resp = self.client.post(url, {"valid_hours": 24}, content_type="application/json", **self.r1_auth)
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertIn("raw_token", data)
        self.assertIn("candidate_url", data)
        self.assertEqual(data["candidate_name"], "Priya Sharma")

    def test_candidate_session_without_token_rejected(self):
        url = reverse("candidate-session")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(resp.json()["error_code"], "TOKEN_REQUIRED")

    def test_candidate_session_with_invalid_token_rejected(self):
        url = reverse("candidate-session")
        resp = self.client.get(url, HTTP_AUTHORIZATION="Bearer invalid-token-12345")
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(resp.json()["error_code"], "INVALID_TOKEN")

    def test_candidate_session_with_revoked_token_rejected(self):
        self.token_obj.is_revoked = True
        self.token_obj.save()

        url = reverse("candidate-session")
        resp = self.client.get(url, **self.candidate_auth)
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.json()["error_code"], "TOKEN_REVOKED")

    def test_candidate_session_with_expired_token_rejected(self):
        self.token_obj.expires_at = timezone.now() - timedelta(minutes=5)
        self.token_obj.save()

        url = reverse("candidate-session")
        resp = self.client.get(url, **self.candidate_auth)
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.json()["error_code"], "TOKEN_EXPIRED")

    def test_candidate_session_success(self):
        url = reverse("candidate-session")
        resp = self.client.get(url, **self.candidate_auth)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["candidate"]["name"], "Priya Sharma")
        self.assertEqual(data["job"]["title"], "Senior Site Reliability Engineer")
        self.assertIn("disclosure", data)
        self.assertTrue(data["disclosure"]["ai_interviewer"])

    # 2. Consent Gating
    def test_candidate_start_rejected_without_consent(self):
        url = reverse("candidate-start")
        resp = self.client.post(url, **self.candidate_auth)
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["error_code"], "CONSENT_NOT_GRANTED")

    def test_candidate_can_grant_consent(self):
        url = reverse("candidate-consent")
        resp = self.client.post(url, {"consent_granted": True}, content_type="application/json", **self.candidate_auth)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["status"], "granted")

        self.candidate.refresh_from_db()
        self.assertEqual(self.candidate.consent_status, Candidate.CONSENT_GRANTED)
        self.assertIsNotNone(self.candidate.consent_recorded_at)

    # 3. Voice Interview Progression (Turn-Based Flow)
    def test_complete_candidate_voice_interview_journey(self):
        # Step A: Grant consent
        consent_url = reverse("candidate-consent")
        self.client.post(consent_url, {"consent_granted": True}, content_type="application/json", **self.candidate_auth)

        # Step B: Start interview
        start_url = reverse("candidate-start")
        resp_start = self.client.post(start_url, **self.candidate_auth)
        self.assertEqual(resp_start.status_code, 200)
        self.assertIn("welcome", resp_start.json()["current_message"].lower())

        # Step C: Synthesize initial greeting speech
        tts_url = reverse("candidate-synthesize-speech")
        resp_tts = self.client.post(
            tts_url,
            {"message": resp_start.json()["current_message"]},
            content_type="application/json",
            **self.candidate_auth,
        )
        self.assertEqual(resp_tts.status_code, 200)
        self.assertEqual(resp_tts["Content-Type"], "audio/wav")

        # Step D: Deliver Q1 by submitting response to intro
        turn_url = reverse("candidate-submit-turn")
        audio_file = SimpleUploadedFile("answer1.wav", self.valid_wav, content_type="audio/wav")
        resp_turn1 = self.client.post(
            turn_url,
            {"audio": audio_file},
            format="multipart",
            **self.candidate_auth,
        )
        self.assertEqual(resp_turn1.status_code, 200)
        data_turn1 = resp_turn1.json()
        self.assertIn("Question 1", data_turn1["interviewer_message"])

        # Step E: Candidate answers Q1 with spoken audio
        audio_file2 = SimpleUploadedFile("answer2.wav", self.valid_wav, content_type="audio/wav")
        resp_turn2 = self.client.post(
            turn_url,
            {"audio": audio_file2},
            format="multipart",
            **self.candidate_auth,
        )
        self.assertEqual(resp_turn2.status_code, 200)
        data_turn2 = resp_turn2.json()
        self.assertIn("interviewer_message", data_turn2)

        # Step F: Candidate answers Q2 -> triggers completion with closing statement
        audio_file3 = SimpleUploadedFile("answer3.wav", self.valid_wav, content_type="audio/wav")
        resp_turn3 = self.client.post(
            turn_url,
            {"audio": audio_file3},
            format="multipart",
            **self.candidate_auth,
        )
        self.assertEqual(resp_turn3.status_code, 200)
        data_turn3 = resp_turn3.json()
        self.assertTrue(data_turn3["is_completed"])
        self.assertIn("closing_statement", self.interview.plan_data)
        self.interview.refresh_from_db()
        self.assertEqual(self.interview.status, Interview.STATUS_COMPLETED)

    # 4. Security & Isolation Tests
    def test_candidate_cannot_access_recruiter_endpoints(self):
        recruiter_interviews_url = reverse("interview-list")
        resp = self.client.get(recruiter_interviews_url, **self.candidate_auth)
        self.assertEqual(resp.status_code, 401)  # Candidate token cannot authenticate as JWT Recruiter

    def test_empty_audio_submission_rejected(self):
        consent_url = reverse("candidate-consent")
        self.client.post(consent_url, {"consent_granted": True}, content_type="application/json", **self.candidate_auth)

        start_url = reverse("candidate-start")
        self.client.post(start_url, **self.candidate_auth)

        turn_url = reverse("candidate-submit-turn")
        empty_audio = SimpleUploadedFile("empty.wav", b"", content_type="audio/wav")
        resp = self.client.post(turn_url, {"audio": empty_audio}, format="multipart", **self.candidate_auth)
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["error_code"], "EMPTY_AUDIO")


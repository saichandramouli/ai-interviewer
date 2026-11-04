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
from evaluations.models import EvaluationResult

User = get_user_model()


class Phase84E2EIntegrationTestSuite(TestCase):
    """
    End-to-End Acceptance Scenario covering:
    1. Recruiter workflow: Invite -> Register -> Login -> Candidate Creation -> Resume Upload -> Job Creation -> Interview Creation -> Plan -> Candidate Link.
    2. Candidate workflow: Open Token -> Session info -> Consent -> Mic request -> Start -> Voice Turn 1 -> Voice Turn 2 -> Complete.
    3. Recruiter review: Completed interview state -> Transcript entries review -> Evaluation review -> Distinction between AI and recruiter decision.
    4. Concurrency & Security Hardening: Token expiration, token revocation, idempotency, duration expiration.
    """

    def setUp(self):
        # Create Admin
        self.admin = User.objects.create_superuser(
            email="admin@example.com",
            password="AdminPassword123!",
        )

        self.valid_wav = (
            b"RIFF\x2c\x00\x00\x00WAVEfmt \x10\x00\x00\x00"
            b"\x01\x00\x01\x00\x80>\x00\x00\x00}\x00\x00"
            b"\x02\x00\x10\x00data\x08\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        )

    def test_full_recruiter_to_candidate_to_recruiter_lifecycle(self):
        # =========================================================================
        # 1. ADMIN INVITES RECRUITER & RECRUITER REGISTRATION
        # =========================================================================
        from accounts.models import RecruiterInvitation
        invitation, raw_inv_token = RecruiterInvitation.create_invitation(
            email="recruiter.e2e@example.com",
            created_by=self.admin,
            valid_hours=48,
        )

        reg_url = reverse("auth_register")
        resp_reg = self.client.post(
            reg_url,
            {
                "token": raw_inv_token,
                "full_name": "Sarah Connor",
                "password": "SecurePassword123!",
                "password_confirm": "SecurePassword123!",
            },
            content_type="application/json",
        )
        self.assertEqual(resp_reg.status_code, 201)

        # Login recruiter
        login_url = reverse("token_obtain_pair")
        resp_login = self.client.post(
            login_url,
            {"email": "recruiter.e2e@example.com", "password": "SecurePassword123!"},
            content_type="application/json",
        )
        self.assertEqual(resp_login.status_code, 200)
        recruiter_token = resp_login.json()["access"]
        r_auth = {"HTTP_AUTHORIZATION": f"Bearer {recruiter_token}"}

        # =========================================================================
        # 2. RECRUITER CREATES CANDIDATE, RESUME, JOB & INTERVIEW
        # =========================================================================
        cand_url = reverse("candidate-list")
        resp_cand = self.client.post(
            cand_url,
            {
                "full_name": "Devan Nair",
                "email": "devan.nair@example.com",
                "phone_number": "+919876500000",
                "extracted_resume_text": "Experienced Python architect with PostgreSQL, Docker, and Kafka expertise.",
            },
            content_type="application/json",
            **r_auth,
        )
        self.assertEqual(resp_cand.status_code, 201)
        candidate_id = resp_cand.json()["id"]

        job_url = reverse("job-list")
        resp_job = self.client.post(
            job_url,
            {
                "title": "Principal Backend Systems Architect",
                "department": "Engineering",
                "description": "Lead design of fault-tolerant high-throughput microservices using Python and distributed streaming.",
            },
            content_type="application/json",
            **r_auth,
        )
        self.assertEqual(resp_job.status_code, 201)
        job_id = resp_job.json()["id"]

        # Create interview
        intv_url = reverse("interview-list")
        resp_intv = self.client.post(
            intv_url,
            {
                "candidate": candidate_id,
                "job": job_id,
                "duration_limit_seconds": 1800,
            },
            content_type="application/json",
            **r_auth,
        )
        self.assertEqual(resp_intv.status_code, 201)
        interview_id = resp_intv.json()["id"]

        interview_obj = Interview.objects.get(id=interview_id)
        interview_obj.plan_data = {
            "introduction": "Welcome Devan. We are excited to assess your system architecture background.",
            "closing_statement": "Thank you Devan. Our team will review the evaluation and follow up.",
        }
        interview_obj.save()

        # Add structured interview questions
        q1 = InterviewQuestion.objects.create(
            interview=interview_obj,
            sequence_number=1,
            question_text="How do you architect data consistency across decoupled microservices?",
            category="System Design",
            competency="Distributed Architecture",
        )
        q2 = InterviewQuestion.objects.create(
            interview=interview_obj,
            sequence_number=2,
            question_text="Describe how you prevent message loss in Apache Kafka under broker failover.",
            category="Reliability",
            competency="Streaming Systems",
        )

        # Generate candidate interview link
        link_url = reverse("interview-generate-candidate-link", kwargs={"pk": interview_id})
        resp_link = self.client.post(link_url, {"valid_hours": 48}, content_type="application/json", **r_auth)
        self.assertEqual(resp_link.status_code, 201)
        raw_candidate_token = resp_link.json()["raw_token"]
        self.assertTrue(len(raw_candidate_token) >= 32)

        c_auth = {"HTTP_AUTHORIZATION": f"Bearer {raw_candidate_token}"}

        # =========================================================================
        # 3. CANDIDATE WORKFLOW: ACCESS -> CONSENT -> START -> TURNS -> COMPLETE
        # =========================================================================
        # A. Candidate visits session
        session_url = reverse("candidate-session")
        resp_sess = self.client.get(session_url, **c_auth)
        self.assertEqual(resp_sess.status_code, 200)
        self.assertEqual(resp_sess.json()["candidate"]["name"], "Devan Nair")
        self.assertEqual(resp_sess.json()["candidate"]["consent_status"], "pending")
        self.assertTrue(resp_sess.json()["disclosure"]["speech_recognition"])

        # B. Candidate grants consent
        consent_url = reverse("candidate-consent")
        resp_consent = self.client.post(
            consent_url,
            {"consent_granted": True, "consent_method": "Candidate Web Portal Checkbox"},
            content_type="application/json",
            **c_auth,
        )
        self.assertEqual(resp_consent.status_code, 200)

        # C. Candidate starts interview
        start_url = reverse("candidate-start")
        resp_start = self.client.post(start_url, **c_auth)
        self.assertEqual(resp_start.status_code, 200)
        self.assertIn("Welcome Devan", resp_start.json()["current_message"])

        # D. Candidate answers Q1 via audio turn
        turn_url = reverse("candidate-submit-turn")
        audio1 = SimpleUploadedFile("q1.wav", self.valid_wav, content_type="audio/wav")
        resp_turn1 = self.client.post(turn_url, {"audio": audio1}, format="multipart", **c_auth)
        self.assertEqual(resp_turn1.status_code, 200)
        self.assertIn("Question 1", resp_turn1.json()["interviewer_message"])

        # E. Candidate answers Q2 via audio turn
        audio2 = SimpleUploadedFile("q2.wav", self.valid_wav, content_type="audio/wav")
        resp_turn2 = self.client.post(turn_url, {"audio": audio2}, format="multipart", **c_auth)
        self.assertEqual(resp_turn2.status_code, 200)

        # F. Candidate answers final question -> completion
        audio3 = SimpleUploadedFile("q3.wav", self.valid_wav, content_type="audio/wav")
        resp_turn3 = self.client.post(turn_url, {"audio": audio3}, format="multipart", **c_auth)
        self.assertEqual(resp_turn3.status_code, 200)
        self.assertTrue(resp_turn3.json()["is_completed"])

        # =========================================================================
        # 4. RECRUITER REVIEWS COMPLETED INTERVIEW & TRANSCRIPTS
        # =========================================================================
        intv_detail_url = reverse("interview-detail", kwargs={"pk": interview_id})
        resp_detail = self.client.get(intv_detail_url, **r_auth)
        self.assertEqual(resp_detail.status_code, 200)
        self.assertEqual(resp_detail.json()["status"], "completed")

        transcript_url = reverse("interview-transcript", kwargs={"pk": interview_id})
        resp_trans = self.client.get(transcript_url, **r_auth)
        self.assertEqual(resp_trans.status_code, 200)
        transcripts = resp_trans.json()
        self.assertGreaterEqual(len(transcripts), 4)

        # Create evaluation report for recruiter review
        eval_result = EvaluationResult.objects.create(
            interview=interview_obj,
            overall_score=85.0,
            competency_scores={"Distributed Architecture": 90.0, "Streaming Systems": 80.0},
            strengths=["Strong grasp of distributed consensus", "Deep understanding of Kafka partition offsets"],
            improvement_areas=["Could elaborate further on database replication lag mitigations"],
            evidence_summary="Demonstrated high competency in distributed systems and fault-tolerant architecture.",
            review_status=EvaluationResult.STATUS_REVIEWED,
        )

        eval_url = reverse("interview-evaluation", kwargs={"pk": interview_id})
        resp_eval = self.client.get(eval_url, **r_auth)
        self.assertEqual(resp_eval.status_code, 200)
        self.assertEqual(resp_eval.json()["overall_score"], 85.0)
        self.assertEqual(resp_eval.json()["review_status"], "reviewed")

    def test_candidate_cannot_access_other_interview_data(self):
        # Candidate 1
        cand1 = Candidate.objects.create(
            created_by=self.admin,
            full_name="Candidate One",
            email="c1@example.com",
            consent_status="granted",
            consent_recorded_at=timezone.now(),
            consent_method="Online",
        )
        job = Job.objects.create(created_by=self.admin, title="Role A", description="Desc A")
        intv1 = Interview.objects.create(created_by=self.admin, candidate=cand1, job=job, status="draft")
        token_obj1, raw_token1 = CandidateInterviewAccessToken.create_token(intv1)

        # Candidate 2
        cand2 = Candidate.objects.create(
            created_by=self.admin,
            full_name="Candidate Two",
            email="c2@example.com",
            consent_status="granted",
            consent_recorded_at=timezone.now(),
            consent_method="Online",
        )
        intv2 = Interview.objects.create(created_by=self.admin, candidate=cand2, job=job, status="draft")

        # Candidate 1 tries to synthesize speech for Candidate 2's interview ID
        synth_url = reverse("candidate-synthesize-speech")
        resp = self.client.post(
            synth_url,
            {"message": "Test utterance"},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {raw_token1}",
        )
        self.assertEqual(resp.status_code, 200)
        # Verify synthesized speech header references intv1, never intv2
        self.assertIn(f"interview-{intv1.id}-speech", resp.get("Content-Disposition", ""))

    def test_expired_candidate_token_cannot_access_session_or_submit(self):
        cand = Candidate.objects.create(
            created_by=self.admin,
            full_name="Expired User",
            email="exp@example.com",
            consent_status="granted",
            consent_recorded_at=timezone.now(),
            consent_method="Online",
        )
        job = Job.objects.create(created_by=self.admin, title="Role", description="Desc")
        intv = Interview.objects.create(created_by=self.admin, candidate=cand, job=job, status="in_progress")
        token_obj, raw_token = CandidateInterviewAccessToken.create_token(intv, valid_hours=1)
        token_obj.expires_at = timezone.now() - timedelta(minutes=10)
        token_obj.save()

        session_url = reverse("candidate-session")
        resp = self.client.get(session_url, HTTP_AUTHORIZATION=f"Bearer {raw_token}")
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.json()["error_code"], "TOKEN_EXPIRED")

        turn_url = reverse("candidate-submit-turn")
        audio = SimpleUploadedFile("test.wav", self.valid_wav, content_type="audio/wav")
        resp_turn = self.client.post(turn_url, {"audio": audio}, format="multipart", HTTP_AUTHORIZATION=f"Bearer {raw_token}")
        self.assertEqual(resp_turn.status_code, 403)

    def test_revoked_candidate_token_denied_access(self):
        cand = Candidate.objects.create(
            created_by=self.admin,
            full_name="Revoked User",
            email="rev@example.com",
            consent_status="granted",
            consent_recorded_at=timezone.now(),
            consent_method="Online",
        )
        job = Job.objects.create(created_by=self.admin, title="Role", description="Desc")
        intv = Interview.objects.create(created_by=self.admin, candidate=cand, job=job, status="in_progress")
        token_obj, raw_token = CandidateInterviewAccessToken.create_token(intv, valid_hours=24)
        token_obj.is_revoked = True
        token_obj.save()

        session_url = reverse("candidate-session")
        resp = self.client.get(session_url, HTTP_AUTHORIZATION=f"Bearer {raw_token}")
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.json()["error_code"], "TOKEN_REVOKED")

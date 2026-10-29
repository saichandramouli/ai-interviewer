import json
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta

from candidates.models import Candidate
from jobs.models import Job
from interviews.models import (
    Interview,
    InterviewQuestion,
    TranscriptEntry,
    InterviewEvent,
    InterviewStatusTransitionError,
)
from integrations.voice.mock_provider import MockVoiceProvider
from interviews.services.orchestrator import (
    InterviewOrchestrationService,
    OrchestrationError,
    ConsentRequiredError,
    PlanRequiredError,
)

User = get_user_model()


class Phase7OrchestrationTestSuite(TestCase):
    def setUp(self):
        self.recruiter1 = User.objects.create_user(
            email="recruiter1@example.com",
            password="Password123!",
        )
        self.recruiter2 = User.objects.create_user(
            email="recruiter2@example.com",
            password="Password123!",
        )

        # JWT Auth for recruiter1
        token_url = reverse("token_obtain_pair")
        resp = self.client.post(
            token_url,
            {"email": "recruiter1@example.com", "password": "Password123!"},
            content_type="application/json",
        )
        self.r1_auth = {"HTTP_AUTHORIZATION": f"Bearer {resp.json()['access']}"}

        # JWT Auth for recruiter2
        resp2 = self.client.post(
            token_url,
            {"email": "recruiter2@example.com", "password": "Password123!"},
            content_type="application/json",
        )
        self.r2_auth = {"HTTP_AUTHORIZATION": f"Bearer {resp2.json()['access']}"}

        # Candidate with verified granted consent
        self.candidate = Candidate.objects.create(
            created_by=self.recruiter1,
            full_name="Bob Test",
            email="bob@example.com",
            phone_number="+15551234567",
            consent_status=Candidate.CONSENT_GRANTED,
            consent_recorded_at=timezone.now(),
            consent_method="Email Form Signed",
        )

        self.job = Job.objects.create(
            created_by=self.recruiter1,
            title="Backend Architect",
            description="Lead microservices architecture with Python.",
        )

        self.interview = Interview.objects.create(
            created_by=self.recruiter1,
            candidate=self.candidate,
            job=self.job,
            status=Interview.STATUS_DRAFT,
            duration_limit_seconds=1800,
            plan_data={
                "introduction": "Welcome Bob. This is your backend interview.",
                "closing_statement": "Thank you for your time. We will be in touch.",
            },
        )

        # Create two ordered questions
        self.q1 = InterviewQuestion.objects.create(
            interview=self.interview,
            sequence_number=1,
            question_text="Describe how you structure high-throughput databases.",
            category="System Design",
            competency="Database Architecture",
        )
        self.q2 = InterviewQuestion.objects.create(
            interview=self.interview,
            sequence_number=2,
            question_text="How do you handle idempotency in event streams?",
            category="Distributed Systems",
            competency="Reliability",
        )

    def test_mock_voice_provider_deterministic_behavior(self):
        provider = MockVoiceProvider()
        self.assertTrue(provider.is_mock)
        self.assertEqual(provider.provider_name, "mock_voice_provider")

        start_res = provider.start_session("intv-1", "+15551234567", 1800)
        self.assertTrue(start_res.is_mock)
        self.assertTrue(start_res.session_id.startswith("mock-call-"))

        q_res = provider.deliver_question(start_res.session_id, 1, "What is ACID?")
        self.assertTrue(q_res.delivered)
        self.assertTrue(q_res.is_mock)

        resp_res = provider.receive_candidate_response(start_res.session_id, simulated_text="ACID ensures reliability.")
        self.assertEqual(resp_res.response_text, "ACID ensures reliability.")

        term_res = provider.end_session(start_res.session_id)
        self.assertEqual(term_res.status, "terminated")

    def test_start_interview_success(self):
        url = reverse("interview-start", kwargs={"pk": str(self.interview.id)})
        resp = self.client.post(url, **self.r1_auth)
        self.assertEqual(resp.status_code, 200)

        data = resp.json()
        self.assertEqual(data["status"], Interview.STATUS_IN_PROGRESS)
        self.assertTrue(data["is_mock"])
        self.assertIn("Simulated mock session only", data["simulation_disclaimer"])
        self.assertIsNotNone(data["provider_call_id"])

        # Verify AI introduction utterance persisted
        transcripts = data["transcripts"]
        self.assertEqual(len(transcripts), 1)
        self.assertEqual(transcripts[0]["speaker"], "ai")
        self.assertEqual(transcripts[0]["text"], self.interview.plan_data["introduction"])

        self.interview.refresh_from_db()
        self.assertEqual(self.interview.status, Interview.STATUS_IN_PROGRESS)
        self.assertIsNotNone(self.interview.started_at)

    def test_start_rejected_without_plan_questions(self):
        self.interview.questions.all().delete()
        url = reverse("interview-start", kwargs={"pk": str(self.interview.id)})
        resp = self.client.post(url, **self.r1_auth)
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["error_code"], "NO_PLAN_QUESTIONS")

    def test_start_rejected_with_pending_or_withdrawn_consent(self):
        # Pending consent
        self.candidate.consent_status = Candidate.CONSENT_PENDING
        self.candidate.save()
        url = reverse("interview-start", kwargs={"pk": str(self.interview.id)})
        resp = self.client.post(url, **self.r1_auth)
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["error_code"], "CONSENT_NOT_GRANTED")

        # Withdrawn consent
        self.candidate.consent_status = Candidate.CONSENT_WITHDRAWN
        self.candidate.save()
        resp2 = self.client.post(url, **self.r1_auth)
        self.assertEqual(resp2.status_code, 400)
        self.assertEqual(resp2.json()["error_code"], "CONSENT_NOT_GRANTED")

    def test_start_rejected_with_unverified_consent(self):
        # Granted but without timestamp
        self.candidate.consent_recorded_at = None
        self.candidate.save()
        url = reverse("interview-start", kwargs={"pk": str(self.interview.id)})
        resp = self.client.post(url, **self.r1_auth)
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["error_code"], "CONSENT_UNVERIFIED")

    def test_recruiter_ownership_isolation(self):
        url = reverse("interview-start", kwargs={"pk": str(self.interview.id)})
        resp = self.client.post(url, **self.r2_auth)
        self.assertEqual(resp.status_code, 404)

        advance_url = reverse("interview-advance", kwargs={"pk": str(self.interview.id)})
        resp_adv = self.client.post(advance_url, **self.r2_auth)
        self.assertEqual(resp_adv.status_code, 404)

        session_url = reverse("interview-session", kwargs={"pk": str(self.interview.id)})
        resp_sess = self.client.get(session_url, **self.r2_auth)
        self.assertEqual(resp_sess.status_code, 404)

    def test_question_progression_lifecycle(self):
        # 1. Start interview
        start_url = reverse("interview-start", kwargs={"pk": str(self.interview.id)})
        self.client.post(start_url, **self.r1_auth)

        # 2. Advance to deliver Question 1
        adv_url = reverse("interview-advance", kwargs={"pk": str(self.interview.id)})
        resp_q1 = self.client.post(adv_url, **self.r1_auth)
        self.assertEqual(resp_q1.status_code, 200)
        data_q1 = resp_q1.json()
        self.assertEqual(len(data_q1["transcripts"]), 2)
        self.assertEqual(data_q1["transcripts"][1]["speaker"], "ai")
        self.assertIn("Question 1", data_q1["transcripts"][1]["text"])

        # 3. Simulate candidate response to Q1 and deliver Question 2
        resp_a1 = self.client.post(
            adv_url,
            {"simulated_response": "I shard databases across clusters by tenant key."},
            content_type="application/json",
            **self.r1_auth,
        )
        self.assertEqual(resp_a1.status_code, 200)
        data_a1 = resp_a1.json()
        self.assertEqual(len(data_a1["transcripts"]), 4)  # intro, Q1, A1, Q2
        self.assertEqual(data_a1["transcripts"][2]["speaker"], "candidate")
        self.assertEqual(data_a1["transcripts"][2]["text"], "I shard databases across clusters by tenant key.")
        self.assertIn("Question 2", data_a1["transcripts"][3]["text"])

        # 4. Simulate response to Q2 and trigger completion with closing statement
        resp_a2 = self.client.post(
            adv_url,
            {"simulated_response": "I use Kafka unique offset keys and distributed deduplication."},
            content_type="application/json",
            **self.r1_auth,
        )
        self.assertEqual(resp_a2.status_code, 200)
        data_a2 = resp_a2.json()
        self.assertEqual(data_a2["status"], Interview.STATUS_COMPLETED)
        # Verify closing statement was appended
        last_entry = data_a2["transcripts"][-1]
        self.assertEqual(last_entry["speaker"], "ai")
        self.assertEqual(last_entry["text"], self.interview.plan_data["closing_statement"])

        self.interview.refresh_from_db()
        self.assertEqual(self.interview.status, Interview.STATUS_COMPLETED)
        self.assertIsNotNone(self.interview.ended_at)

    def test_transcript_sequence_uniqueness(self):
        start_url = reverse("interview-start", kwargs={"pk": str(self.interview.id)})
        self.client.post(start_url, **self.r1_auth)

        adv_url = reverse("interview-advance", kwargs={"pk": str(self.interview.id)})
        self.client.post(adv_url, **self.r1_auth)
        self.client.post(
            adv_url,
            {"simulated_response": "Answer one."},
            content_type="application/json",
            **self.r1_auth,
        )

        entries = list(TranscriptEntry.objects.filter(interview=self.interview).order_by("sequence_number"))
        seq_numbers = [e.sequence_number for e in entries]
        self.assertEqual(seq_numbers, list(range(1, len(entries) + 1)))
        self.assertEqual(len(seq_numbers), len(set(seq_numbers)))

    def test_idempotent_event_replay(self):
        start_url = reverse("interview-start", kwargs={"pk": str(self.interview.id)})
        key = "idemp-test-key-12345"

        # First start
        resp1 = self.client.post(
            start_url,
            HTTP_IDEMPOTENCY_KEY=key,
            **self.r1_auth,
        )
        self.assertEqual(resp1.status_code, 200)

        # Duplicate start with same idempotency key
        resp2 = self.client.post(
            start_url,
            HTTP_IDEMPOTENCY_KEY=key,
            **self.r1_auth,
        )
        self.assertEqual(resp2.status_code, 200)
        self.assertIn("already processed", resp2.json()["message"])

        # Verify event was recorded
        event = InterviewEvent.objects.filter(interview=self.interview, idempotency_key=key).first()
        self.assertIsNotNone(event)
        self.assertEqual(event.processing_status, InterviewEvent.STATUS_PROCESSED)

    def test_simulated_candidate_disconnect(self):
        start_url = reverse("interview-start", kwargs={"pk": str(self.interview.id)})
        self.client.post(start_url, **self.r1_auth)

        adv_url = reverse("interview-advance", kwargs={"pk": str(self.interview.id)})
        resp = self.client.post(
            adv_url,
            {"simulate_disconnect": True},
            content_type="application/json",
            **self.r1_auth,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["status"], Interview.STATUS_FAILED)

        self.interview.refresh_from_db()
        self.assertEqual(self.interview.status, Interview.STATUS_FAILED)

    def test_interview_cancellation(self):
        start_url = reverse("interview-start", kwargs={"pk": str(self.interview.id)})
        self.client.post(start_url, **self.r1_auth)

        cancel_url = reverse("interview-cancel", kwargs={"pk": str(self.interview.id)})
        resp = self.client.post(
            cancel_url,
            {"reason": "Recruiter emergency cancellation."},
            content_type="application/json",
            **self.r1_auth,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["status"], Interview.STATUS_CANCELLED)

        # Cannot advance after cancellation
        adv_url = reverse("interview-advance", kwargs={"pk": str(self.interview.id)})
        resp_adv = self.client.post(adv_url, **self.r1_auth)
        self.assertEqual(resp_adv.status_code, 400)

    def test_time_limit_expiration_handling(self):
        start_url = reverse("interview-start", kwargs={"pk": str(self.interview.id)})
        self.client.post(start_url, **self.r1_auth)

        # Simulate 31 minutes elapsed (exceeding 30m / 1800s duration limit)
        self.interview.refresh_from_db()
        self.interview.started_at = timezone.now() - timedelta(seconds=1860)
        self.interview.save(update_fields=["started_at"])

        adv_url = reverse("interview-advance", kwargs={"pk": str(self.interview.id)})
        resp = self.client.post(adv_url, **self.r1_auth)
        self.assertEqual(resp.status_code, 200)
        # Should conclude automatically
        self.assertEqual(resp.json()["status"], Interview.STATUS_COMPLETED)
        self.assertIn("Time limit expired", resp.json()["message"])

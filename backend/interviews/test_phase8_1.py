import json
from unittest.mock import patch, MagicMock
import requests
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from candidates.models import Candidate
from jobs.models import Job
from interviews.models import (
    Interview,
    InterviewQuestion,
    TranscriptEntry,
    InterviewEvent,
)
from interviews.services.dialogue_service import (
    NemotronDialogueService,
    DialogueTurnResponse,
)
from interviews.services.orchestrator import InterviewOrchestrationService

User = get_user_model()


class Phase81DialogueTestSuite(TestCase):
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

        resp2 = self.client.post(
            token_url,
            {"email": "recruiter2@example.com", "password": "Password123!"},
            content_type="application/json",
        )
        self.r2_auth = {"HTTP_AUTHORIZATION": f"Bearer {resp2.json()['access']}"}

        self.candidate = Candidate.objects.create(
            created_by=self.recruiter1,
            full_name="Alice Developer",
            email="alice@example.com",
            phone_number="+15559876543",
            consent_status=Candidate.CONSENT_GRANTED,
            consent_recorded_at=timezone.now(),
            consent_method="Online Consent Portal",
        )

        self.job = Job.objects.create(
            created_by=self.recruiter1,
            title="Senior Distributed Systems Engineer",
            description="Design fault-tolerant distributed consensus systems.",
        )

        self.interview = Interview.objects.create(
            created_by=self.recruiter1,
            candidate=self.candidate,
            job=self.job,
            status=Interview.STATUS_DRAFT,
            duration_limit_seconds=1800,
            plan_data={
                "introduction": "Hello Alice, welcome to your distributed systems interview.",
                "closing_statement": "Thank you Alice, our team will review the session and reach out.",
            },
        )

        self.q1 = InterviewQuestion.objects.create(
            interview=self.interview,
            sequence_number=1,
            question_text="How would you design a distributed consensus mechanism like Raft?",
            category="System Design",
            competency="Distributed Systems",
            expected_evidence="Leader election, log replication, split brain prevention",
            suggested_follow_up="How do you handle network partitions between leader and followers?",
        )
        self.q2 = InterviewQuestion.objects.create(
            interview=self.interview,
            sequence_number=2,
            question_text="Describe your experience tuning database connection pooling under heavy load.",
            category="Performance",
            competency="Database Reliability",
            expected_evidence="Connection starvation, pool sizing formulas, timeouts",
            suggested_follow_up="What metrics do you monitor to detect connection leaks?",
        )

    # 1. Dialogue Service Unit Tests
    @patch("requests.Session.post")
    def test_nemotron_successful_dialogue_turn(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps({
                            "message": "That's a solid start. Could you explain specifically how Raft prevents split-brain during a network partition?",
                            "response_type": "follow_up",
                            "next_action": "follow_up",
                            "related_question_id": self.q1.id,
                            "evaluation_notes": "Candidate mentioned leader election but omitted quorum details."
                        }),
                        "reasoning_content": "The candidate provided a basic definition of Raft. A quorum question is necessary."
                    }
                }
            ]
        }
        mock_post.return_value = mock_response

        service = NemotronDialogueService(api_key="test-key")
        turn = service.generate_dialogue_turn(
            interview=self.interview,
            candidate_response_text="Raft uses a leader to replicate log entries across servers.",
            current_question=self.q1,
            elapsed_seconds=120,
            allow_follow_up=True,
        )

        self.assertEqual(turn.response_type, "follow_up")
        self.assertEqual(turn.next_action, "follow_up")
        self.assertEqual(turn.related_question_id, self.q1.id)
        self.assertIn("prevents split-brain", turn.message)
        # Verify reasoning_content is NOT in evaluation_notes or message
        self.assertNotIn("The candidate provided a basic definition", turn.message)
        self.assertNotIn("The candidate provided a basic definition", turn.evaluation_notes or "")

    @patch("requests.Session.post")
    def test_strict_isolation_reasoning_content_discarded(self, mock_post):
        """Verify that internal chain-of-thought is discarded and never retained."""
        sensitive_reasoning = "SECRET_CHAIN_OF_THOUGHT: internal candidate rating = 7/10."
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps({
                            "message": "Thank you for explaining your approach.",
                            "response_type": "question",
                            "next_action": "continue",
                            "related_question_id": self.q1.id,
                            "evaluation_notes": "Candidate provided adequate answer."
                        }),
                        "reasoning_content": sensitive_reasoning,
                    }
                }
            ]
        }
        mock_post.return_value = mock_response

        service = NemotronDialogueService(api_key="test-key")
        turn = service.generate_dialogue_turn(
            interview=self.interview,
            candidate_response_text="We configured Raft with 3 nodes.",
            current_question=self.q1,
        )

        self.assertNotIn("SECRET_CHAIN_OF_THOUGHT", turn.message)
        self.assertNotIn("SECRET_CHAIN_OF_THOUGHT", str(turn.evaluation_notes))
        # Ensure dialogue turn response object has no reasoning attribute
        self.assertFalse(hasattr(turn, "reasoning_content"))

    @patch("requests.Session.post")
    def test_timeout_fallback_to_plan_question(self, mock_post):
        """If NVIDIA API times out, safe deterministic fallback must occur."""
        mock_post.side_effect = requests.exceptions.Timeout("Connection timed out after 30s")

        service = NemotronDialogueService(api_key="test-key")
        turn = service.generate_dialogue_turn(
            interview=self.interview,
            candidate_response_text="Some answer",
            current_question=self.q1,
        )

        self.assertIsNotNone(turn)
        self.assertEqual(turn.next_action, "continue")
        self.assertIn(self.q1.question_text, turn.message)
        self.assertIn("fallback", turn.evaluation_notes.lower())

    @patch("requests.Session.post")
    def test_rate_limit_429_fallback(self, mock_post):
        """If NVIDIA API returns 429 Too Many Requests, safe fallback must occur."""
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.text = "Rate limit exceeded"
        mock_post.return_value = mock_response

        service = NemotronDialogueService(api_key="test-key")
        turn = service.generate_dialogue_turn(
            interview=self.interview,
            candidate_response_text="Some answer",
            current_question=self.q1,
        )

        self.assertIsNotNone(turn)
        self.assertEqual(turn.next_action, "continue")
        self.assertIn(self.q1.question_text, turn.message)

    @patch("requests.Session.post")
    def test_malformed_json_fallback(self, mock_post):
        """If model returns malformed JSON or plain text, safe fallback must occur."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": "Not a JSON document at all! Just raw plain text.",
                        "reasoning_content": "Just thinking..."
                    }
                }
            ]
        }
        mock_post.return_value = mock_response

        service = NemotronDialogueService(api_key="test-key")
        turn = service.generate_dialogue_turn(
            interview=self.interview,
            candidate_response_text="Some answer",
            current_question=self.q1,
        )

        self.assertIsNotNone(turn)
        self.assertEqual(turn.next_action, "continue")
        self.assertIn(self.q1.question_text, turn.message)

    # 2. Orchestrator Integration & Progression Tests
    @patch("requests.Session.post")
    def test_orchestrator_follow_up_turn_flow(self, mock_post):
        """Candidate answers Q1 -> Nemotron requests follow-up -> delivered in transcript -> candidate answers -> moves to Q2."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps({
                            "message": "How do you handle split brain if two partitions claim to be leader?",
                            "response_type": "follow_up",
                            "next_action": "follow_up",
                            "related_question_id": self.q1.id,
                            "evaluation_notes": "Probing quorum partition handling."
                        })
                    }
                }
            ]
        }
        mock_post.return_value = mock_response

        start_url = reverse("interview-start", kwargs={"pk": str(self.interview.id)})
        self.client.post(start_url, **self.r1_auth)

        adv_url = reverse("interview-advance", kwargs={"pk": str(self.interview.id)})
        # Deliver Q1
        self.client.post(adv_url, **self.r1_auth)

        # Candidate answers Q1
        resp_a1 = self.client.post(
            adv_url,
            {"simulated_response": "I would use a Raft consensus cluster."},
            content_type="application/json",
            **self.r1_auth,
        )
        self.assertEqual(resp_a1.status_code, 200)
        data = resp_a1.json()
        transcripts = data["transcripts"]
        # Transcripts: Intro (1), Q1 (2), Candidate A1 (3), Follow-up AI (4)
        self.assertEqual(len(transcripts), 4)
        self.assertEqual(transcripts[3]["speaker"], "ai")
        self.assertIn("Follow-up:", transcripts[3]["text"])
        self.assertIn("split brain", transcripts[3]["text"])

        # Candidate answers the follow-up -> Orchestrator must advance to Q2 (capping at 1 follow-up)
        resp_a_follow = self.client.post(
            adv_url,
            {"simulated_response": "Only the partition with a majority quorum can elect a leader."},
            content_type="application/json",
            **self.r1_auth,
        )
        self.assertEqual(resp_a_follow.status_code, 200)
        data2 = resp_a_follow.json()
        transcripts2 = data2["transcripts"]
        # Transcripts: Intro (1), Q1 (2), Candidate A1 (3), Follow-up AI (4), Candidate Follow-up Ans (5), Q2 (6)
        self.assertEqual(len(transcripts2), 6)
        self.assertEqual(transcripts2[5]["speaker"], "ai")
        self.assertIn("Question 2", transcripts2[5]["text"])

    @patch("requests.Session.post")
    def test_mock_voice_provider_preserved_and_unaltered(self, mock_post):
        """Ensures MockVoiceProvider remains intact and active during session advancement."""
        start_url = reverse("interview-start", kwargs={"pk": str(self.interview.id)})
        resp = self.client.post(start_url, **self.r1_auth)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["is_mock"])
        self.assertIn("mock-call-", data["provider_call_id"])
        self.assertIn("Simulated mock session only", data["simulation_disclaimer"])

    def test_recruiter_isolation_enforced(self):
        """Recruiter 2 cannot advance Recruiter 1's interview."""
        start_url = reverse("interview-start", kwargs={"pk": str(self.interview.id)})
        self.client.post(start_url, **self.r1_auth)

        adv_url = reverse("interview-advance", kwargs={"pk": str(self.interview.id)})
        resp = self.client.post(
            adv_url,
            {"simulated_response": "Hacking attempt from other recruiter"},
            content_type="application/json",
            **self.r2_auth,
        )
        self.assertEqual(resp.status_code, 404)


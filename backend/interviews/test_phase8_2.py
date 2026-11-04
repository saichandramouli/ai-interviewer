import json
from unittest.mock import patch, MagicMock
from io import BytesIO
import requests
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from django.core.files.uploadedfile import SimpleUploadedFile

from candidates.models import Candidate
from jobs.models import Job
from interviews.models import (
    Interview,
    InterviewQuestion,
    TranscriptEntry,
)
from integrations.speech.base import (
    STTResult,
    TTSResult,
    AudioValidationError,
    STTError,
    TTSError,
    ProviderTimeoutError,
    ProviderRateLimitError,
)
from integrations.speech.stt.base import BaseSTTProvider
from integrations.speech.stt.mock import MockSTTProvider
from integrations.speech.stt.deepgram import DeepgramSTTProvider
from integrations.speech.tts.base import BaseTTSProvider
from integrations.speech.tts.mock import MockTTSProvider
from integrations.speech.tts.elevenlabs import ElevenLabsTTSProvider
from integrations.speech.factory import SpeechProviderFactory

User = get_user_model()


class Phase82SpeechTestSuite(TestCase):
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
            full_name="Rajesh Kumar",
            email="rajesh@example.com",
            phone_number="+919876543210",
            consent_status=Candidate.CONSENT_GRANTED,
            consent_recorded_at=timezone.now(),
            consent_method="Online Consent Form",
        )

        self.job = Job.objects.create(
            created_by=self.recruiter1,
            title="Senior Backend Engineer",
            description="Build resilient distributed cloud services in Python.",
        )

        self.interview = Interview.objects.create(
            created_by=self.recruiter1,
            candidate=self.candidate,
            job=self.job,
            status=Interview.STATUS_IN_PROGRESS,
            duration_limit_seconds=1800,
            plan_data={
                "introduction": "Hello Rajesh, welcome to the technical interview.",
                "closing_statement": "Thank you Rajesh, our team will get back to you shortly.",
            },
        )

        self.transcript_ai = TranscriptEntry.objects.create(
            interview=self.interview,
            sequence_number=1,
            speaker=TranscriptEntry.SPEAKER_AI,
            text="Can you describe how you architect high-volume Kafka streaming pipelines?",
            timestamp=timezone.now(),
        )

        # Valid mock wav bytes
        self.valid_wav_bytes = (
            b"RIFF\x2c\x00\x00\x00WAVEfmt \x10\x00\x00\x00"
            b"\x01\x00\x01\x00\x80>\x00\x00\x00}\x00\x00"
            b"\x02\x00\x10\x00data\x08\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        )

    # ==========================================
    # 1. STT Provider Tests
    # ==========================================
    def test_mock_stt_successful_transcription(self):
        provider = MockSTTProvider(default_transcript="I shard Kafka topics by customer ID.")
        result = provider.transcribe(
            audio_bytes=self.valid_wav_bytes,
            content_type="audio/wav",
            language="en-IN",
        )
        self.assertEqual(result.text, "I shard Kafka topics by customer ID.")
        self.assertEqual(result.provider_name, "mock_stt")
        self.assertFalse(result.is_empty)
        self.assertGreater(result.confidence, 0.9)

    def test_stt_empty_audio_rejected(self):
        provider = MockSTTProvider()
        with self.assertRaises(AudioValidationError) as ctx:
            provider.transcribe(audio_bytes=b"", content_type="audio/wav")
        self.assertEqual(ctx.exception.error_code, "EMPTY_AUDIO")

    def test_stt_invalid_format_rejected(self):
        provider = MockSTTProvider()
        with self.assertRaises(AudioValidationError) as ctx:
            provider.transcribe(audio_bytes=b"dummy", content_type="text/plain")
        self.assertEqual(ctx.exception.error_code, "UNSUPPORTED_AUDIO_FORMAT")

    def test_stt_oversized_audio_rejected(self):
        provider = MockSTTProvider()
        large_payload = b"x" * (26 * 1024 * 1024)  # 26 MB exceeds 25 MB limit
        with self.assertRaises(AudioValidationError) as ctx:
            provider.transcribe(audio_bytes=large_payload, content_type="audio/wav")
        self.assertEqual(ctx.exception.error_code, "AUDIO_TOO_LARGE")

    @patch("requests.Session.post")
    def test_deepgram_successful_transcription(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "metadata": {"duration": 4.5},
            "results": {
                "channels": [
                    {
                        "alternatives": [
                            {
                                "transcript": "We implement distributed tracing using OpenTelemetry.",
                                "confidence": 0.97
                            }
                        ]
                    }
                ]
            }
        }
        mock_post.return_value = mock_response

        provider = DeepgramSTTProvider(api_key="test-deepgram-key")
        result = provider.transcribe(
            audio_bytes=self.valid_wav_bytes,
            content_type="audio/wav",
            language="en-IN",
        )
        self.assertEqual(result.text, "We implement distributed tracing using OpenTelemetry.")
        self.assertEqual(result.provider_name, "deepgram")
        self.assertEqual(result.confidence, 0.97)
        self.assertEqual(result.duration_seconds, 4.5)

    @patch("requests.Session.post")
    def test_deepgram_timeout_handling(self, mock_post):
        mock_post.side_effect = requests.exceptions.Timeout("Deepgram timed out")
        provider = DeepgramSTTProvider(api_key="test-key")
        with self.assertRaises(ProviderTimeoutError) as ctx:
            provider.transcribe(audio_bytes=self.valid_wav_bytes, content_type="audio/wav")
        self.assertEqual(ctx.exception.error_code, "STT_TIMEOUT")

    @patch("requests.Session.post")
    def test_deepgram_rate_limit_handling(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_post.return_value = mock_response
        provider = DeepgramSTTProvider(api_key="test-key")
        with self.assertRaises(ProviderRateLimitError) as ctx:
            provider.transcribe(audio_bytes=self.valid_wav_bytes, content_type="audio/wav")
        self.assertEqual(ctx.exception.error_code, "STT_RATE_LIMIT")

    @patch("requests.Session.post")
    def test_deepgram_malformed_json_handling(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_post.return_value = mock_response
        provider = DeepgramSTTProvider(api_key="test-key")
        with self.assertRaises(STTError) as ctx:
            provider.transcribe(audio_bytes=self.valid_wav_bytes, content_type="audio/wav")
        self.assertEqual(ctx.exception.error_code, "STT_PARSE_ERROR")

    # ==========================================
    # 2. TTS Provider Tests
    # ==========================================
    def test_mock_tts_successful_synthesis(self):
        provider = MockTTSProvider()
        result = provider.synthesize(
            text="Could you elaborate on your indexing strategy?",
            language="en-IN",
        )
        self.assertEqual(result.provider_name, "mock_tts")
        self.assertEqual(result.audio_format, "audio/wav")
        self.assertGreater(len(result.audio_bytes), 0)
        self.assertGreater(result.duration_seconds, 0)

    def test_tts_empty_text_rejected(self):
        provider = MockTTSProvider()
        with self.assertRaises(AudioValidationError) as ctx:
            provider.synthesize(text="")
        self.assertEqual(ctx.exception.error_code, "EMPTY_TEXT")

    def test_tts_oversized_text_rejected(self):
        provider = MockTTSProvider()
        with self.assertRaises(AudioValidationError) as ctx:
            provider.synthesize(text="A" * 4500)
        self.assertEqual(ctx.exception.error_code, "TEXT_TOO_LONG")

    @patch("requests.Session.post")
    def test_elevenlabs_successful_synthesis(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"ID3_MOCK_MP3_AUDIO_BYTES_TEST"
        mock_post.return_value = mock_response

        provider = ElevenLabsTTSProvider(api_key="test-elevenlabs-key")
        result = provider.synthesize(
            text="How do you handle schema migrations without downtime?",
            language="en-IN",
        )
        self.assertEqual(result.provider_name, "elevenlabs")
        self.assertEqual(result.audio_format, "audio/mpeg")
        self.assertEqual(result.audio_bytes, b"ID3_MOCK_MP3_AUDIO_BYTES_TEST")

    @patch("requests.Session.post")
    def test_elevenlabs_timeout_handling(self, mock_post):
        mock_post.side_effect = requests.exceptions.Timeout("ElevenLabs timed out")
        provider = ElevenLabsTTSProvider(api_key="test-key")
        with self.assertRaises(ProviderTimeoutError) as ctx:
            provider.synthesize(text="Testing timeout.")
        self.assertEqual(ctx.exception.error_code, "TTS_TIMEOUT")

    @patch("requests.Session.post")
    def test_elevenlabs_rate_limit_handling(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_post.return_value = mock_response
        provider = ElevenLabsTTSProvider(api_key="test-key")
        with self.assertRaises(ProviderRateLimitError) as ctx:
            provider.synthesize(text="Testing rate limit.")
        self.assertEqual(ctx.exception.error_code, "TTS_RATE_LIMIT")

    # ==========================================
    # 3. Security, Consent & Ownership API Tests
    # ==========================================
    def test_transcribe_audio_endpoint_success(self):
        url = reverse("interview-transcribe-audio", kwargs={"pk": str(self.interview.id)})
        audio_file = SimpleUploadedFile("candidate.wav", self.valid_wav_bytes, content_type="audio/wav")

        resp = self.client.post(url, {"audio": audio_file}, format="multipart", **self.r1_auth)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("text", data)
        self.assertEqual(data["interview_id"], str(self.interview.id))
        self.assertFalse(data["is_empty"])

    def test_transcribe_audio_missing_consent_rejected(self):
        self.candidate.consent_status = Candidate.CONSENT_PENDING
        self.candidate.save()

        url = reverse("interview-transcribe-audio", kwargs={"pk": str(self.interview.id)})
        audio_file = SimpleUploadedFile("candidate.wav", self.valid_wav_bytes, content_type="audio/wav")

        resp = self.client.post(url, {"audio": audio_file}, format="multipart", **self.r1_auth)
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["error_code"], "CONSENT_NOT_GRANTED")

    def test_transcribe_audio_cross_recruiter_denied(self):
        url = reverse("interview-transcribe-audio", kwargs={"pk": str(self.interview.id)})
        audio_file = SimpleUploadedFile("candidate.wav", self.valid_wav_bytes, content_type="audio/wav")

        resp = self.client.post(url, {"audio": audio_file}, format="multipart", **self.r2_auth)
        self.assertEqual(resp.status_code, 404)

    def test_transcribe_audio_unauthenticated_denied(self):
        url = reverse("interview-transcribe-audio", kwargs={"pk": str(self.interview.id)})
        audio_file = SimpleUploadedFile("candidate.wav", self.valid_wav_bytes, content_type="audio/wav")

        resp = self.client.post(url, {"audio": audio_file}, format="multipart")
        self.assertEqual(resp.status_code, 401)

    def test_synthesize_speech_endpoint_success(self):
        url = reverse("interview-synthesize-speech", kwargs={"pk": str(self.interview.id)})
        resp = self.client.post(
            url,
            {"transcript_id": self.transcript_ai.id},
            content_type="application/json",
            **self.r1_auth,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "audio/wav")
        self.assertGreater(len(resp.content), 0)

    def test_synthesize_speech_empty_message_rejected(self):
        url = reverse("interview-synthesize-speech", kwargs={"pk": str(self.interview.id)})
        resp = self.client.post(
            url,
            {"message": "   "},
            content_type="application/json",
            **self.r1_auth,
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["error_code"], "EMPTY_MESSAGE")

    def test_synthesize_speech_cross_recruiter_denied(self):
        url = reverse("interview-synthesize-speech", kwargs={"pk": str(self.interview.id)})
        resp = self.client.post(
            url,
            {"message": "Test question."},
            content_type="application/json",
            **self.r2_auth,
        )
        self.assertEqual(resp.status_code, 404)


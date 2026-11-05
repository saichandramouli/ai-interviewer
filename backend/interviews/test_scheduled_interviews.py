from datetime import timedelta
import zoneinfo
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from candidates.models import Candidate
from jobs.models import Job
from interviews.models import Interview

User = get_user_model()


class ScheduledInterviewCreationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='recruiter@example.com',
            password='TestPassword123!',
        )
        self.candidate = Candidate.objects.create(
            full_name='Jane Doe',
            email='jane.doe@example.com',
            consent_status=Candidate.CONSENT_GRANTED,
            created_by=self.user,
        )
        self.job = Job.objects.create(
            title='Senior Backend Engineer',
            description='Django, Celery, and API development',
            required_skills=['Python', 'Django'],
            created_by=self.user,
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_manual_interview_creation_retains_draft_status(self):
        """Manual interview creation works without scheduled_at and defaults to draft status."""
        resp = self.client.post('/api/v1/interviews/', {
            'candidate': str(self.candidate.id),
            'job': str(self.job.id),
            'initiation_type': 'manual',
            'duration_limit_seconds': 1800,
        })
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertEqual(data['status'], 'draft')
        self.assertEqual(data['initiation_type'], 'manual')
        self.assertIsNone(data['scheduled_at'])

        interview = Interview.objects.get(id=data['id'])
        self.assertEqual(interview.status, Interview.STATUS_DRAFT)

    def test_scheduled_interview_creation_with_valid_future_datetime(self):
        """Scheduled interview creation with valid future date and timezone sets status to scheduled."""
        future_time = timezone.now() + timedelta(days=2, hours=3)
        future_iso = future_time.isoformat()

        resp = self.client.post('/api/v1/interviews/', {
            'candidate': str(self.candidate.id),
            'job': str(self.job.id),
            'initiation_type': 'scheduled',
            'scheduled_at': future_iso,
            'timezone': 'Asia/Kolkata',
            'duration_limit_seconds': 2400,
        })
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertEqual(data['status'], 'scheduled')
        self.assertEqual(data['initiation_type'], 'scheduled')
        self.assertEqual(data['timezone'], 'Asia/Kolkata')
        self.assertIsNotNone(data['scheduled_at'])

        interview = Interview.objects.get(id=data['id'])
        self.assertEqual(interview.status, Interview.STATUS_SCHEDULED)
        self.assertEqual(interview.timezone, 'Asia/Kolkata')

    def test_scheduled_interview_without_scheduled_at_is_rejected(self):
        """Scheduled mode without scheduled_at must be rejected with 400 Bad Request."""
        resp = self.client.post('/api/v1/interviews/', {
            'candidate': str(self.candidate.id),
            'job': str(self.job.id),
            'initiation_type': 'scheduled',
        })
        self.assertEqual(resp.status_code, 400)
        data = resp.json()
        self.assertIn('scheduled_at', data)

    def test_scheduled_interview_with_past_datetime_is_rejected(self):
        """Scheduled mode with a past datetime must be rejected."""
        past_time = timezone.now() - timedelta(hours=1)
        resp = self.client.post('/api/v1/interviews/', {
            'candidate': str(self.candidate.id),
            'job': str(self.job.id),
            'initiation_type': 'scheduled',
            'scheduled_at': past_time.isoformat(),
            'timezone': 'UTC',
        })
        self.assertEqual(resp.status_code, 400)
        data = resp.json()
        self.assertIn('scheduled_at', data)
        self.assertIn('future', str(data['scheduled_at']))

    def test_scheduled_interview_with_invalid_timezone_is_rejected(self):
        """Invalid IANA timezone string must be rejected."""
        future_time = timezone.now() + timedelta(days=1)
        resp = self.client.post('/api/v1/interviews/', {
            'candidate': str(self.candidate.id),
            'job': str(self.job.id),
            'initiation_type': 'scheduled',
            'scheduled_at': future_time.isoformat(),
            'timezone': 'Invalid/NonExistent_Zone',
        })
        self.assertEqual(resp.status_code, 400)
        data = resp.json()
        self.assertIn('timezone', data)
        self.assertIn('valid IANA timezone', str(data['timezone']))

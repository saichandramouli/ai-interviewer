import zoneinfo
from django.utils import timezone
from rest_framework import serializers
from interviews.models import Interview, InterviewQuestion, TranscriptEntry, InterviewStatusTransitionError
from candidates.models import Candidate
from jobs.models import Job


class InterviewQuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = InterviewQuestion
        fields = [
            'id',
            'sequence_number',
            'question_text',
            'category',
            'competency',
            'expected_evidence',
            'suggested_follow_up',
            'estimated_minutes',
            'max_score',
        ]
        read_only_fields = ['id']


class TranscriptEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = TranscriptEntry
        fields = [
            'id',
            'sequence_number',
            'speaker',
            'text',
            'timestamp',
        ]
        read_only_fields = ['id']


class InterviewListSerializer(serializers.ModelSerializer):
    candidate_name = serializers.ReadOnlyField(source='candidate.full_name')
    job_title = serializers.ReadOnlyField(source='job.title')

    class Meta:
        model = Interview
        fields = [
            'id',
            'candidate',
            'candidate_name',
            'job',
            'job_title',
            'status',
            'initiation_type',
            'scheduled_at',
            'timezone',
            'duration_limit_seconds',
            'started_at',
            'ended_at',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class InterviewDetailSerializer(serializers.ModelSerializer):
    candidate_name = serializers.ReadOnlyField(source='candidate.full_name')
    job_title = serializers.ReadOnlyField(source='job.title')

    class Meta:
        model = Interview
        fields = [
            'id',
            'candidate',
            'candidate_name',
            'job',
            'job_title',
            'status',
            'initiation_type',
            'scheduled_at',
            'timezone',
            'duration_limit_seconds',
            'started_at',
            'ended_at',
            'provider_call_id',
            'plan_data',
            'created_by',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_by', 'created_at', 'updated_at']

    def validate(self, attrs):
        request = self.context.get('request')
        user = request.user if request else None

        # Cross-recruiter validation on create / update
        candidate = attrs.get('candidate')
        if candidate and candidate.created_by != user:
            raise serializers.ValidationError(
                {"candidate": "Candidate does not exist or belongs to another recruiter."}
            )

        job = attrs.get('job')
        if job and job.created_by != user:
            raise serializers.ValidationError(
                {"job": "Job does not exist or belongs to another recruiter."}
            )

        # Status transition validation on update
        if self.instance and 'status' in attrs:
            new_status = attrs['status']
            try:
                self.instance.validate_transition(new_status)
            except InterviewStatusTransitionError as err:
                raise serializers.ValidationError({"status": str(err)})

        # Scheduled interview validation
        initiation_type = attrs.get('initiation_type') or (self.instance.initiation_type if self.instance else Interview.INITIATION_MANUAL)
        if initiation_type == Interview.INITIATION_SCHEDULED:
            scheduled_at = attrs.get('scheduled_at') or (self.instance.scheduled_at if self.instance else None)
            if not scheduled_at:
                raise serializers.ValidationError(
                    {"scheduled_at": "scheduled_at is mandatory when initiation_type is 'scheduled'."}
                )

            # Validate timezone identifier if provided
            tz_str = attrs.get('timezone') or (self.instance.timezone if self.instance else 'UTC')
            try:
                zoneinfo.ZoneInfo(tz_str)
            except Exception:
                raise serializers.ValidationError(
                    {"timezone": f"'{tz_str}' is not a valid IANA timezone identifier."}
                )

            # Reject past scheduled dates
            now = timezone.now()
            if scheduled_at <= now:
                raise serializers.ValidationError(
                    {"scheduled_at": "Scheduled interview date and time must be in the future."}
                )

        return attrs

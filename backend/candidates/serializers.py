from rest_framework import serializers
from candidates.models import Candidate


class CandidateListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Candidate
        fields = [
            'id',
            'full_name',
            'email',
            'phone_number',
            'consent_status',
            'consent_recorded_at',
            'consent_method',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class CandidateDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = Candidate
        fields = [
            'id',
            'full_name',
            'email',
            'phone_number',
            'resume',
            'extracted_resume_text',
            'consent_status',
            'consent_recorded_at',
            'consent_method',
            'created_by',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_by', 'created_at', 'updated_at']

    def validate_consent_status(self, value):
        valid = [Candidate.CONSENT_PENDING, Candidate.CONSENT_GRANTED, Candidate.CONSENT_WITHDRAWN]
        if value not in valid:
            raise serializers.ValidationError(f"Invalid consent status. Choices: {valid}")
        return value

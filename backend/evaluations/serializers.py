from rest_framework import serializers
from evaluations.models import EvaluationResult


class EvaluationResultSerializer(serializers.ModelSerializer):
    reviewed_by_email = serializers.EmailField(source='reviewed_by.email', read_only=True)
    reviewed_by_name = serializers.CharField(source='reviewed_by.get_full_name', read_only=True)

    class Meta:
        model = EvaluationResult
        fields = [
            'id',
            'interview',
            'overall_score',
            'competency_scores',
            'strengths',
            'improvement_areas',
            'evidence_summary',
            'review_status',
            'evaluation_status',
            'error_message',
            'recruiter_notes',
            'final_decision',
            'reviewed_by',
            'reviewed_by_email',
            'reviewed_by_name',
            'reviewed_at',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'interview',
            'evaluation_status',
            'error_message',
            'review_status',
            'reviewed_by',
            'reviewed_at',
            'created_at',
            'updated_at',
        ]

    def validate_overall_score(self, value):
        if value is not None and not (0.0 <= value <= 100.0):
            raise serializers.ValidationError("overall_score must be between 0 and 100.")
        return value

    def validate_competency_scores(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("competency_scores must be a JSON object/dictionary.")
        return value

    def validate_strengths(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("strengths must be a JSON list.")
        return value

    def validate_improvement_areas(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("improvement_areas must be a JSON list.")
        return value

from rest_framework import serializers
from evaluations.models import EvaluationResult


class EvaluationResultSerializer(serializers.ModelSerializer):
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
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'interview', 'created_at', 'updated_at']

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

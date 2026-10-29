from rest_framework import serializers
from jobs.models import Job


class JobSerializer(serializers.ModelSerializer):
    class Meta:
        model = Job
        fields = [
            'id',
            'title',
            'description',
            'required_skills',
            'experience_requirements',
            'is_active',
            'created_by',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_by', 'created_at', 'updated_at']

    def validate_required_skills(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("required_skills must be a list of skill strings.")
        return value

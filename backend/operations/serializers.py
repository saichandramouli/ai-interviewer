from rest_framework import serializers
from operations.models import AsyncOperation


class AsyncOperationStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = AsyncOperation
        fields = [
            'id',
            'operation_type',
            'status',
            'status_message',
            'error_code',
            'candidate',
            'interview',
            'attempt_count',
            'created_at',
            'started_at',
            'completed_at',
        ]
        read_only_fields = fields

from rest_framework import viewsets, permissions, mixins
from operations.models import AsyncOperation
from operations.serializers import AsyncOperationStatusSerializer


class AsyncOperationViewSet(
    mixins.RetrieveModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = AsyncOperationStatusSerializer

    def get_queryset(self):
        # Strict recruiter ownership isolation
        return AsyncOperation.objects.filter(created_by=self.request.user)

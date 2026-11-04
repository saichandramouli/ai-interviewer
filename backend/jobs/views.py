from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from accounts.permissions import IsRecruiterUser
from jobs.models import Job
from jobs.serializers import JobSerializer


class JobViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated, IsRecruiterUser]
    serializer_class = JobSerializer

    def get_queryset(self):
        return Job.objects.filter(created_by=self.request.user)

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def destroy(self, request, *args, **kwargs):
        job = self.get_object()
        if job.interviews.exists():
            return Response(
                {"detail": "Cannot delete job with associated interviews. Mark it inactive instead."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().destroy(request, *args, **kwargs)

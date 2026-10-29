from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework import status
from django.db import connection


class HealthCheckView(APIView):
    """
    Lightweight health check endpoint performing database connectivity verification.
    Returns HTTP 200 if healthy, HTTP 503 if database check fails.
    Sensitive details and stack traces are excluded.
    """

    permission_classes = [AllowAny]

    def get(self, request):
        db_healthy = False
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1;")
                row = cursor.fetchone()
                if row and row[0] == 1:
                    db_healthy = True
        except Exception:
            db_healthy = False

        if db_healthy:
            return Response(
                {
                    "status": "healthy",
                    "database": "connected",
                },
                status=status.HTTP_200_OK,
            )

        return Response(
            {
                "status": "unhealthy",
                "database": "disconnected",
            },
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

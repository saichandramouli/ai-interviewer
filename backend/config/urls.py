from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)
from config.views import HealthCheckView
from candidates.views import CandidateViewSet
from jobs.views import JobViewSet
from interviews.views import InterviewViewSet
from operations.views import AsyncOperationViewSet

router = DefaultRouter()
router.register(r'candidates', CandidateViewSet, basename='candidate')
router.register(r'jobs', JobViewSet, basename='job')
router.register(r'interviews', InterviewViewSet, basename='interview')
router.register(r'operations', AsyncOperationViewSet, basename='operation')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/health/', HealthCheckView.as_view(), name='health-check'),

    # JWT Authentication Endpoints
    path('api/v1/auth/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/v1/auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/v1/auth/token/verify/', TokenVerifyView.as_view(), name='token_verify'),

    # Core Resource Endpoints
    path('api/v1/', include(router.urls)),
]

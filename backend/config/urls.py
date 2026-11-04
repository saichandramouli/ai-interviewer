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
from accounts.views import (
    CurrentUserView,
    AdminUserManagementViewSet,
    AdminInvitationViewSet,
    ValidateInvitationView,
    RegisterWithInvitationView,
)
from interviews.candidate_views import (
    CandidateSessionView,
    CandidateConsentView,
    CandidateStartInterviewView,
    CandidateSubmitTurnView,
    CandidateSynthesizeSpeechView,
)

router = DefaultRouter()
router.register(r'candidates', CandidateViewSet, basename='candidate')
router.register(r'jobs', JobViewSet, basename='job')
router.register(r'interviews', InterviewViewSet, basename='interview')
router.register(r'operations', AsyncOperationViewSet, basename='operation')
router.register(r'admin/users', AdminUserManagementViewSet, basename='admin-user')
router.register(r'admin/invitations', AdminInvitationViewSet, basename='admin-invitation')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/health/', HealthCheckView.as_view(), name='health-check'),

    # JWT Authentication Endpoints
    path('api/v1/auth/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/v1/auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/v1/auth/token/verify/', TokenVerifyView.as_view(), name='token_verify'),
    path('api/v1/auth/me/', CurrentUserView.as_view(), name='auth_current_user'),

    # Invitation & Registration Endpoints
    path('api/v1/auth/invitations/validate/', ValidateInvitationView.as_view(), name='auth_validate_invitation'),
    path('api/v1/auth/register/', RegisterWithInvitationView.as_view(), name='auth_register'),

    # Candidate Voice Interview Endpoints (Token-Authenticated)
    path('api/v1/candidate/session/', CandidateSessionView.as_view(), name='candidate-session'),
    path('api/v1/candidate/consent/', CandidateConsentView.as_view(), name='candidate-consent'),
    path('api/v1/candidate/start/', CandidateStartInterviewView.as_view(), name='candidate-start'),
    path('api/v1/candidate/submit-turn/', CandidateSubmitTurnView.as_view(), name='candidate-submit-turn'),
    path('api/v1/candidate/synthesize-speech/', CandidateSynthesizeSpeechView.as_view(), name='candidate-synthesize-speech'),

    # Core Resource Endpoints
    path('api/v1/', include(router.urls)),
]

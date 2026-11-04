from rest_framework import views, viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.throttling import ScopedRateThrottle
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from accounts.models import RecruiterInvitation
from accounts.permissions import IsAdminUser
from accounts.serializers import (
    UserSummarySerializer,
    RecruiterInvitationListSerializer,
    CreateInvitationSerializer,
    RegisterWithInvitationSerializer,
)

User = get_user_model()


class CurrentUserView(views.APIView):
    """
    Returns profile information for the authenticated user, including their role.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        serializer = UserSummarySerializer(request.user)
        return Response(serializer.data)


class AdminUserManagementViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Admin-only endpoint to list registered users and their roles/statuses,
    and activate/deactivate recruiter accounts safely.
    """
    permission_classes = [IsAdminUser]
    serializer_class = UserSummarySerializer
    queryset = User.objects.all().order_by('-date_joined')

    @action(detail=True, methods=['post'], url_path='toggle-active')
    def toggle_active(self, request, pk=None):
        user = self.get_object()
        # Prevent admin from deactivating their own account
        if user.id == request.user.id:
            return Response(
                {"detail": "You cannot modify the active status of your own administrator account."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # Prevent deactivating other superusers/admins
        if user.is_superuser or user.is_staff:
            return Response(
                {"detail": "Cannot modify active status of other administrator accounts."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user.is_active = not user.is_active
        user.save(update_fields=['is_active'])
        return Response(UserSummarySerializer(user).data)


class AdminInvitationViewSet(viewsets.ModelViewSet):
    """
    Admin-only endpoint to create, list, and revoke recruiter invitations.
    """
    permission_classes = [IsAdminUser]
    serializer_class = RecruiterInvitationListSerializer
    queryset = RecruiterInvitation.objects.all().select_related('created_by', 'registered_user')

    def create(self, request, *args, **kwargs):
        serializer = CreateInvitationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data['email']
        invitation, raw_token = RecruiterInvitation.create_invitation(
            email=email,
            created_by=request.user,
            valid_hours=48,
        )

        response_data = RecruiterInvitationListSerializer(invitation).data
        response_data['raw_token'] = raw_token
        # Construct registration URL for admin convenience
        response_data['registration_url'] = f"/register?token={raw_token}"

        return Response(response_data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='revoke')
    def revoke(self, request, pk=None):
        invitation = self.get_object()
        if invitation.status == RecruiterInvitation.STATUS_USED:
            return Response(
                {"detail": "Cannot revoke an invitation that has already been used."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        invitation.is_revoked = True
        invitation.save(update_fields=['is_revoked'])
        return Response(RecruiterInvitationListSerializer(invitation).data)


class ValidateInvitationView(views.APIView):
    """
    Public endpoint: Validates an invitation token before registration form is submitted.
    Does not require authentication. Rate limited to prevent token enumeration.
    """
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'invitations'

    def get(self, request):
        token = request.query_params.get('token', '').strip()
        if not token:
            return Response(
                {"detail": "Invitation token is required.", "valid": False},
                status=status.HTTP_400_BAD_REQUEST,
            )

        token_hash = RecruiterInvitation.hash_token(token)
        try:
            invitation = RecruiterInvitation.objects.get(token_hash=token_hash)
        except RecruiterInvitation.DoesNotExist:
            return Response(
                {"detail": "Invalid or unrecognized invitation token.", "valid": False},
                status=status.HTTP_404_NOT_FOUND,
            )

        if invitation.is_revoked:
            return Response(
                {"detail": "This invitation has been revoked by an administrator.", "valid": False, "status": "revoked"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if invitation.used_at is not None or invitation.registered_user is not None:
            return Response(
                {"detail": "This invitation has already been used.", "valid": False, "status": "used"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if timezone.now() >= invitation.expires_at:
            return Response(
                {"detail": "This invitation has expired.", "valid": False, "status": "expired"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Invitation is valid! Return the invited email
        return Response(
            {
                "valid": True,
                "email": invitation.email,
                "expires_at": invitation.expires_at,
                "status": "pending",
            },
            status=status.HTTP_200_OK,
        )


class RegisterWithInvitationView(views.APIView):
    """
    Public endpoint: Creates a new Recruiter user using a valid, unused invitation token.
    Uses atomic transaction and row locking to guarantee single-use. Rate limited.
    """
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'invitations'

    def post(self, request):
        serializer = RegisterWithInvitationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        token = serializer.validated_data['token'].strip()
        full_name = serializer.validated_data['full_name'].strip()
        password = serializer.validated_data['password']

        token_hash = RecruiterInvitation.hash_token(token)

        # Atomic transaction with row locking
        with transaction.atomic():
            invitation = (
                RecruiterInvitation.objects.select_for_update()
                .filter(token_hash=token_hash)
                .first()
            )

            if not invitation or not invitation.is_valid:
                return Response(
                    {"detail": "Invitation is no longer valid, has expired, or was already used."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Split full_name into first_name and last_name
            parts = full_name.split(' ', 1)
            first_name = parts[0]
            last_name = parts[1] if len(parts) > 1 else ''

            # Create new user - ALWAYS as Recruiter (is_staff=False, is_superuser=False)
            user = User.objects.create_user(
                email=invitation.email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                is_staff=False,
                is_superuser=False,
                is_active=True,
            )

            # Mark invitation as used
            invitation.used_at = timezone.now()
            invitation.registered_user = user
            invitation.save(update_fields=['used_at', 'registered_user'])

        return Response(
            {
                "message": "Registration successful. You can now log in.",
                "email": user.email,
                "role": user.role,
            },
            status=status.HTTP_201_CREATED,
        )

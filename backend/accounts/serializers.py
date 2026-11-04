from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from accounts.models import RecruiterInvitation

User = get_user_model()


class UserSummarySerializer(serializers.ModelSerializer):
    """Serializer for admin viewing registered users."""
    role = serializers.CharField(read_only=True)
    status = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id',
            'email',
            'first_name',
            'last_name',
            'role',
            'is_active',
            'status',
            'date_joined',
            'last_login',
        ]
        read_only_fields = fields

    def get_status(self, obj):
        return "active" if obj.is_active else "inactive"


class RecruiterInvitationListSerializer(serializers.ModelSerializer):
    """Serializer for admin viewing invitations."""
    status = serializers.CharField(read_only=True)
    created_by_email = serializers.EmailField(source='created_by.email', read_only=True)
    registered_user_email = serializers.EmailField(source='registered_user.email', read_only=True)

    class Meta:
        model = RecruiterInvitation
        fields = [
            'id',
            'email',
            'status',
            'created_at',
            'expires_at',
            'used_at',
            'is_revoked',
            'created_by_email',
            'registered_user_email',
        ]
        read_only_fields = fields


class CreateInvitationSerializer(serializers.Serializer):
    """Serializer for admin generating a recruiter invitation."""
    email = serializers.EmailField()

    def validate_email(self, value):
        normalized = value.strip().lower()
        if User.objects.filter(email=normalized).exists():
            raise serializers.ValidationError("A user with this email address is already registered.")
        
        # Check if an active, unexpired, non-revoked invitation already exists for this email
        active_invitation = RecruiterInvitation.objects.filter(
            email=normalized,
            is_revoked=False,
            used_at__isnull=True,
            expires_at__gt=timezone.now(),
        ).first()
        if active_invitation:
            raise serializers.ValidationError(
                "An active, unexpired invitation already exists for this email address. Revoke it before issuing a new one."
            )
        return normalized


class ValidateInvitationSerializer(serializers.Serializer):
    """Serializer for candidate/recruiter validating an invitation token."""
    token = serializers.CharField(write_only=True)
    email = serializers.EmailField(read_only=True)
    status = serializers.CharField(read_only=True)
    expires_at = serializers.DateTimeField(read_only=True)


class RegisterWithInvitationSerializer(serializers.Serializer):
    """Serializer for completing registration with a valid invitation token."""
    token = serializers.CharField(write_only=True)
    full_name = serializers.CharField(max_length=255, required=True)
    password = serializers.CharField(write_only=True, required=True)
    password_confirm = serializers.CharField(write_only=True, required=True)

    def validate(self, attrs):
        token = attrs.get('token', '').strip()
        password = attrs.get('password')
        password_confirm = attrs.get('password_confirm')
        full_name = attrs.get('full_name', '').strip()

        if not full_name:
            raise serializers.ValidationError({'full_name': 'Full name is required.'})

        if password != password_confirm:
            raise serializers.ValidationError({'password_confirm': 'Passwords do not match.'})

        # Validate password against Django password validators
        try:
            validate_password(password)
        except DjangoValidationError as err:
            raise serializers.ValidationError({'password': list(err.messages)})

        # Validate token
        token_hash = RecruiterInvitation.hash_token(token)
        try:
            invitation = RecruiterInvitation.objects.get(token_hash=token_hash)
        except RecruiterInvitation.DoesNotExist:
            raise serializers.ValidationError({'token': 'Invalid or unrecognized invitation token.'})

        if invitation.is_revoked:
            raise serializers.ValidationError({'token': 'This invitation has been revoked by an administrator.'})
        if invitation.used_at is not None or invitation.registered_user is not None:
            raise serializers.ValidationError({'token': 'This invitation has already been used to register an account.'})
        if timezone.now() >= invitation.expires_at:
            raise serializers.ValidationError({'token': 'This invitation has expired. Please request a new invitation.'})

        # Verify that the email is not already registered
        if User.objects.filter(email=invitation.email).exists():
            raise serializers.ValidationError({'email': f"An account with {invitation.email} already exists."})

        attrs['invitation'] = invitation
        return attrs


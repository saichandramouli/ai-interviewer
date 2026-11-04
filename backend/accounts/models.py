from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from datetime import timedelta
import hashlib
import secrets


class CustomUserManager(BaseUserManager):
    """
    Custom user model manager where email is the unique identifier
    for authentication instead of usernames.
    """

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError(_("The Email field must be set"))
        email = self.normalize_email(email)
        extra_fields.setdefault("is_active", True)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError(_("Superuser must have is_staff=True."))
        if extra_fields.get("is_superuser") is not True:
            raise ValueError(_("Superuser must have is_superuser=True."))

        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    """
    Custom User model where email is the unique identifier for authentication.
    The username field is removed.
    """

    username = None
    email = models.EmailField(_("email address"), unique=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = CustomUserManager()

    def __str__(self):
        return self.email

    @property
    def role(self):
        """Role identifier: 'admin' for superuser/staff, 'recruiter' for standard users."""
        if self.is_superuser or self.is_staff:
            return "admin"
        return "recruiter"


class RecruiterInvitation(models.Model):
    """
    Admin-generated single-use invitation for recruiter onboarding.
    The raw token is never persisted; only its SHA-256 hash is stored.
    """

    STATUS_PENDING = "pending"
    STATUS_USED = "used"
    STATUS_EXPIRED = "expired"
    STATUS_REVOKED = "revoked"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_USED, "Used"),
        (STATUS_EXPIRED, "Expired"),
        (STATUS_REVOKED, "Revoked"),
    ]

    email = models.EmailField(_("invited email address"))
    token_hash = models.CharField(max_length=64, unique=True, db_index=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="created_invitations",
    )
    created_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    registered_user = models.OneToOneField(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="invitation",
    )
    is_revoked = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["email", "is_revoked"]),
        ]

    def __str__(self):
        return f"Invitation for {self.email} ({self.status})"

    @staticmethod
    def hash_token(raw_token: str) -> str:
        """Computes the SHA-256 digest of a raw invitation token."""
        return hashlib.sha256(raw_token.strip().encode("utf-8")).hexdigest()

    @classmethod
    def create_invitation(cls, email: str, created_by: User, valid_hours: int = 48):
        """
        Generates a cryptographically secure random token, hashes it,
        and saves the invitation. Returns the tuple: (invitation_instance, raw_token).
        """
        raw_token = secrets.token_urlsafe(32)
        token_hash = cls.hash_token(raw_token)
        expires_at = timezone.now() + timedelta(hours=valid_hours)

        invitation = cls.objects.create(
            email=email.strip().lower(),
            token_hash=token_hash,
            created_by=created_by,
            expires_at=expires_at,
        )
        return invitation, raw_token

    @property
    def status(self) -> str:
        if self.is_revoked:
            return self.STATUS_REVOKED
        if self.used_at is not None or self.registered_user is not None:
            return self.STATUS_USED
        if timezone.now() >= self.expires_at:
            return self.STATUS_EXPIRED
        return self.STATUS_PENDING

    @property
    def is_valid(self) -> bool:
        """True only if pending, unexpired, and not revoked."""
        return self.status == self.STATUS_PENDING

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from unittest.mock import patch
from accounts.models import RecruiterInvitation
from candidates.models import Candidate
from jobs.models import Job
from interviews.models import Interview

User = get_user_model()


class UserModelTests(TestCase):
    def test_create_user_with_email_successful(self):
        user = User.objects.create_user(
            email="test@example.com",
            password="testpassword123",
        )
        self.assertEqual(user.email, "test@example.com")
        self.assertTrue(user.check_password("testpassword123"))
        self.assertTrue(user.is_active)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertEqual(user.role, "recruiter")

    def test_create_user_without_email_raises_error(self):
        with self.assertRaises(ValueError):
            User.objects.create_user(email="", password="testpassword123")

    def test_create_superuser_successful(self):
        admin_user = User.objects.create_superuser(
            email="admin@example.com",
            password="adminpassword123",
        )
        self.assertEqual(admin_user.email, "admin@example.com")
        self.assertTrue(admin_user.is_staff)
        self.assertTrue(admin_user.is_superuser)
        self.assertEqual(admin_user.role, "admin")


class HealthCheckTests(TestCase):
    def test_health_check_endpoint_healthy(self):
        url = reverse("health-check")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"status": "healthy", "database": "connected"},
        )

    @patch("django.db.connection.cursor")
    def test_health_check_endpoint_db_failure(self, mock_cursor):
        mock_cursor.side_effect = Exception("Database unreachable")
        url = reverse("health-check")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json(),
            {"status": "unhealthy", "database": "disconnected"},
        )


class RecruiterInvitationAndRegistrationTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            email="admin@example.com",
            password="AdminPassword123!",
        )
        self.recruiter = User.objects.create_user(
            email="recruiter@example.com",
            password="RecruiterPassword123!",
        )
        self.recruiter2 = User.objects.create_user(
            email="recruiter2@example.com",
            password="RecruiterPassword123!",
        )

        # Login tokens
        token_url = reverse("token_obtain_pair")
        resp_admin = self.client.post(token_url, {"email": "admin@example.com", "password": "AdminPassword123!"})
        self.admin_auth = {"HTTP_AUTHORIZATION": f"Bearer {resp_admin.json()['access']}"}

        resp_recruiter = self.client.post(token_url, {"email": "recruiter@example.com", "password": "RecruiterPassword123!"})
        self.recruiter_auth = {"HTTP_AUTHORIZATION": f"Bearer {resp_recruiter.json()['access']}"}
        self.recruiter_refresh = resp_recruiter.json()['refresh']
        self.recruiter_access = resp_recruiter.json()['access']

        resp_recruiter2 = self.client.post(token_url, {"email": "recruiter2@example.com", "password": "RecruiterPassword123!"})
        self.recruiter2_auth = {"HTTP_AUTHORIZATION": f"Bearer {resp_recruiter2.json()['access']}"}

    def test_current_user_me_endpoint(self):
        url = reverse("auth_current_user")
        resp = self.client.get(url, **self.admin_auth)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["email"], "admin@example.com")
        self.assertEqual(resp.json()["role"], "admin")

        resp2 = self.client.get(url, **self.recruiter_auth)
        self.assertEqual(resp2.status_code, 200)
        self.assertEqual(resp2.json()["email"], "recruiter@example.com")
        self.assertEqual(resp2.json()["role"], "recruiter")

    def test_inactive_user_cannot_login(self):
        inactive_user = User.objects.create_user(
            email="inactive@example.com",
            password="Password123!",
            is_active=False,
        )
        token_url = reverse("token_obtain_pair")
        resp = self.client.post(token_url, {"email": "inactive@example.com", "password": "Password123!"})
        self.assertEqual(resp.status_code, 401)

    def test_deactivated_user_cannot_access_apis_with_existing_token(self):
        # Deactivate recruiter
        self.recruiter.is_active = False
        self.recruiter.save()

        # Attempt API access with old token
        url = reverse("auth_current_user")
        resp = self.client.get(url, **self.recruiter_auth)
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(resp.json()["code"], "user_inactive")

    def test_deactivated_user_cannot_refresh_token(self):
        # Deactivate recruiter
        self.recruiter.is_active = False
        self.recruiter.save()

        # Attempt token refresh
        refresh_url = reverse("token_refresh")
        resp = self.client.post(refresh_url, {"refresh": self.recruiter_refresh})
        self.assertEqual(resp.status_code, 401)

    def test_admin_can_create_invitation(self):
        url = reverse("admin-invitation-list")
        resp = self.client.post(
            url,
            {"email": "newrecruiter@example.com"},
            format="json",
            **self.admin_auth,
        )
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertEqual(data["email"], "newrecruiter@example.com")
        self.assertIn("raw_token", data)
        self.assertTrue(data["raw_token"])
        self.assertEqual(data["status"], "pending")

        # Verify hash was stored, not raw token
        inv = RecruiterInvitation.objects.get(email="newrecruiter@example.com")
        self.assertNotEqual(inv.token_hash, data["raw_token"])
        self.assertEqual(inv.token_hash, RecruiterInvitation.hash_token(data["raw_token"]))
        self.assertEqual(inv.created_by, self.admin)

    def test_recruiter_cannot_create_invitation(self):
        url = reverse("admin-invitation-list")
        resp = self.client.post(
            url,
            {"email": "another@example.com"},
            format="json",
            **self.recruiter_auth,
        )
        self.assertEqual(resp.status_code, 403)

    def test_unauthenticated_user_cannot_create_invitation(self):
        url = reverse("admin-invitation-list")
        resp = self.client.post(
            url,
            {"email": "another@example.com"},
            format="json",
        )
        self.assertEqual(resp.status_code, 401)

    def test_valid_invitation_allows_registration_and_creates_recruiter(self):
        inv, raw_token = RecruiterInvitation.create_invitation("invited@example.com", self.admin)

        # Validate token first
        val_url = reverse("auth_validate_invitation") + f"?token={raw_token}"
        val_resp = self.client.get(val_url)
        self.assertEqual(val_resp.status_code, 200)
        self.assertTrue(val_resp.json()["valid"])
        self.assertEqual(val_resp.json()["email"], "invited@example.com")

        # Register
        reg_url = reverse("auth_register")
        reg_resp = self.client.post(
            reg_url,
            {
                "token": raw_token,
                "full_name": "Jane Doe",
                "password": "StrongPassword123!",
                "password_confirm": "StrongPassword123!",
            },
            format="json",
        )
        self.assertEqual(reg_resp.status_code, 201)
        self.assertEqual(reg_resp.json()["role"], "recruiter")

        # Check DB user
        user = User.objects.get(email="invited@example.com")
        self.assertEqual(user.first_name, "Jane")
        self.assertEqual(user.last_name, "Doe")
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertEqual(user.role, "recruiter")

        # Check invitation marked as used
        inv.refresh_from_db()
        self.assertEqual(inv.status, RecruiterInvitation.STATUS_USED)
        self.assertEqual(inv.registered_user, user)
        self.assertIsNotNone(inv.used_at)

        # Log in with the newly created account
        token_url = reverse("token_obtain_pair")
        login_resp = self.client.post(
            token_url,
            {"email": "invited@example.com", "password": "StrongPassword123!"},
        )
        self.assertEqual(login_resp.status_code, 200)
        self.assertIn("access", login_resp.json())

    def test_registration_cannot_grant_admin_privileges(self):
        inv, raw_token = RecruiterInvitation.create_invitation("attacker@example.com", self.admin)
        reg_url = reverse("auth_register")
        # Attempt tampering by passing is_staff / is_superuser / role
        reg_resp = self.client.post(
            reg_url,
            {
                "token": raw_token,
                "full_name": "Attacker",
                "password": "StrongPassword123!",
                "password_confirm": "StrongPassword123!",
                "is_staff": True,
                "is_superuser": True,
                "role": "admin",
            },
            format="json",
        )
        self.assertEqual(reg_resp.status_code, 201)
        user = User.objects.get(email="attacker@example.com")
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertEqual(user.role, "recruiter")

    def test_invalid_invitation_token_is_rejected(self):
        val_url = reverse("auth_validate_invitation") + "?token=completely-invalid-token"
        val_resp = self.client.get(val_url)
        self.assertEqual(val_resp.status_code, 404)
        self.assertFalse(val_resp.json()["valid"])

        reg_url = reverse("auth_register")
        reg_resp = self.client.post(
            reg_url,
            {
                "token": "completely-invalid-token",
                "full_name": "Test User",
                "password": "StrongPassword123!",
                "password_confirm": "StrongPassword123!",
            },
            format="json",
        )
        self.assertEqual(reg_resp.status_code, 400)

    def test_expired_invitation_is_rejected(self):
        inv, raw_token = RecruiterInvitation.create_invitation("expired@example.com", self.admin)
        inv.expires_at = timezone.now() - timedelta(minutes=1)
        inv.save()

        val_url = reverse("auth_validate_invitation") + f"?token={raw_token}"
        val_resp = self.client.get(val_url)
        self.assertEqual(val_resp.status_code, 400)
        self.assertFalse(val_resp.json()["valid"])
        self.assertEqual(val_resp.json()["status"], "expired")

        reg_url = reverse("auth_register")
        reg_resp = self.client.post(
            reg_url,
            {
                "token": raw_token,
                "full_name": "Expired User",
                "password": "StrongPassword123!",
                "password_confirm": "StrongPassword123!",
            },
            format="json",
        )
        self.assertEqual(reg_resp.status_code, 400)

    def test_revoked_invitation_is_rejected(self):
        inv, raw_token = RecruiterInvitation.create_invitation("revoked@example.com", self.admin)
        
        # Admin revokes it
        revoke_url = reverse("admin-invitation-revoke", kwargs={"pk": inv.id})
        rev_resp = self.client.post(revoke_url, **self.admin_auth)
        self.assertEqual(rev_resp.status_code, 200)
        self.assertEqual(rev_resp.json()["status"], "revoked")

        # Validation check
        val_url = reverse("auth_validate_invitation") + f"?token={raw_token}"
        val_resp = self.client.get(val_url)
        self.assertEqual(val_resp.status_code, 400)
        self.assertFalse(val_resp.json()["valid"])

        # Registration attempt
        reg_url = reverse("auth_register")
        reg_resp = self.client.post(
            reg_url,
            {
                "token": raw_token,
                "full_name": "Revoked User",
                "password": "StrongPassword123!",
                "password_confirm": "StrongPassword123!",
            },
            format="json",
        )
        self.assertEqual(reg_resp.status_code, 400)

    def test_used_invitation_cannot_be_reused(self):
        inv, raw_token = RecruiterInvitation.create_invitation("once@example.com", self.admin)

        # First use
        reg_url = reverse("auth_register")
        reg1 = self.client.post(
            reg_url,
            {
                "token": raw_token,
                "full_name": "First Use",
                "password": "StrongPassword123!",
                "password_confirm": "StrongPassword123!",
            },
            format="json",
        )
        self.assertEqual(reg1.status_code, 201)

        # Second attempt with same token
        reg2 = self.client.post(
            reg_url,
            {
                "token": raw_token,
                "full_name": "Second Use",
                "password": "StrongPassword123!",
                "password_confirm": "StrongPassword123!",
            },
            format="json",
        )
        self.assertEqual(reg2.status_code, 400)

    def test_duplicate_email_rejected_on_invitation_creation(self):
        # recruiter@example.com already exists from setUp
        url = reverse("admin-invitation-list")
        resp = self.client.post(
            url,
            {"email": "recruiter@example.com"},
            format="json",
            **self.admin_auth,
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("already registered", resp.json()["email"][0])

    def test_admin_can_view_users_list(self):
        url = reverse("admin-user-list")
        resp = self.client.get(url, **self.admin_auth)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        users_list = data["results"] if "results" in data else data
        emails = [u["email"] for u in users_list]
        self.assertIn("admin@example.com", emails)
        self.assertIn("recruiter@example.com", emails)

    def test_admin_can_toggle_recruiter_active_status(self):
        toggle_url = reverse("admin-user-toggle-active", kwargs={"pk": self.recruiter.id})
        resp = self.client.post(toggle_url, **self.admin_auth)
        self.assertEqual(resp.status_code, 200)
        self.recruiter.refresh_from_db()
        self.assertFalse(self.recruiter.is_active)

        # Toggle back to active
        resp2 = self.client.post(toggle_url, **self.admin_auth)
        self.assertEqual(resp2.status_code, 200)
        self.recruiter.refresh_from_db()
        self.assertTrue(self.recruiter.is_active)

    def test_admin_cannot_deactivate_self(self):
        toggle_url = reverse("admin-user-toggle-active", kwargs={"pk": self.admin.id})
        resp = self.client.post(toggle_url, **self.admin_auth)
        self.assertEqual(resp.status_code, 400)

    def test_recruiter_cannot_view_admin_users_list(self):
        url = reverse("admin-user-list")
        resp = self.client.get(url, **self.recruiter_auth)
        self.assertEqual(resp.status_code, 403)

    def test_admin_cannot_create_candidates(self):
        url = reverse("candidate-list")
        resp = self.client.post(
            url,
            {"full_name": "Admin Candidate", "email": "cand@example.com"},
            format="json",
            **self.admin_auth,
        )
        self.assertEqual(resp.status_code, 403)

    def test_admin_cannot_create_jobs(self):
        url = reverse("job-list")
        resp = self.client.post(
            url,
            {"title": "Admin Job", "description": "Desc"},
            format="json",
            **self.admin_auth,
        )
        self.assertEqual(resp.status_code, 403)

    def test_admin_cannot_create_interviews(self):
        url = reverse("interview-list")
        resp = self.client.post(
            url,
            {"duration_limit_seconds": 1800},
            format="json",
            **self.admin_auth,
        )
        self.assertEqual(resp.status_code, 403)

    def test_recruiter_can_create_candidates_and_jobs(self):
        cand_url = reverse("candidate-list")
        c_resp = self.client.post(
            cand_url,
            {"full_name": "Valid Candidate", "email": "validcand@example.com"},
            format="json",
            **self.recruiter_auth,
        )
        self.assertEqual(c_resp.status_code, 201)

        job_url = reverse("job-list")
        j_resp = self.client.post(
            job_url,
            {"title": "Valid Job", "description": "Job description"},
            format="json",
            **self.recruiter_auth,
        )
        self.assertEqual(j_resp.status_code, 201)

    def test_recruiter_cross_recruiter_interview_assignment_rejected(self):
        # Recruiter 2 creates candidate & job
        c2 = Candidate.objects.create(full_name="Candidate Two", email="c2@example.com", created_by=self.recruiter2)
        j2 = Job.objects.create(title="Job Two", description="Desc 2", created_by=self.recruiter2)

        # Recruiter 1 tries to create interview with Recruiter 2's candidate
        intv_url = reverse("interview-list")
        resp = self.client.post(
            intv_url,
            {"candidate": str(c2.id), "job": str(j2.id), "duration_limit_seconds": 1800},
            format="json",
            **self.recruiter_auth,
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("candidate", resp.json())

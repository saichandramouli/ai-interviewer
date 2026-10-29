from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from unittest.mock import patch


class UserModelTests(TestCase):
    def test_create_user_with_email_successful(self):
        User = get_user_model()
        user = User.objects.create_user(
            email="test@example.com",
            password="testpassword123",
        )
        self.assertEqual(user.email, "test@example.com")
        self.assertTrue(user.check_password("testpassword123"))
        self.assertTrue(user.is_active)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertFalse(hasattr(user, "username") and user.username is not None)

    def test_create_user_without_email_raises_error(self):
        User = get_user_model()
        with self.assertRaises(ValueError):
            User.objects.create_user(email="", password="testpassword123")

    def test_create_superuser_successful(self):
        User = get_user_model()
        admin_user = User.objects.create_superuser(
            email="admin@example.com",
            password="adminpassword123",
        )
        self.assertEqual(admin_user.email, "admin@example.com")
        self.assertTrue(admin_user.is_staff)
        self.assertTrue(admin_user.is_superuser)


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

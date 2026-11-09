import json

import json

from django.test import Client, TestCase

from .models import User


class AuthenticationAPITests(TestCase):
    def post_json(self, path, data):
        return self.client.post(
            path,
            data=json.dumps(data),
            content_type="application/json",
        )

    def test_registration_creates_user_and_session(self):
        response = self.post_json(
            "/api/auth/register/",
            {
                "phone": "+242 06 123 4567",
                "email": "client@example.com",
                "password": "SecureStrongPass!927",
            },
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(User.objects.get().phone, "+242061234567")
        self.assertIn("_auth_user_id", self.client.session)

    def test_registration_rejects_duplicate_phone(self):
        User.objects.create_user(phone="+242061234567", password="SecureStrongPass!927")

        response = self.post_json(
            "/api/auth/register/",
            {
                "phone": "+242 06 123 4567",
                "password": "AnotherSecurePass!927",
            },
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(User.objects.count(), 1)

    def test_login_and_logout(self):
        User.objects.create_user(phone="+242061234567", password="SecureStrongPass!927")

        login_response = self.post_json(
            "/api/auth/login/",
            {"phone": "+242 06 123 4567", "password": "SecureStrongPass!927"},
        )
        self.assertEqual(login_response.status_code, 200)
        self.assertIn("_auth_user_id", self.client.session)

        logout_response = self.post_json("/api/auth/logout/", {})
        self.assertEqual(logout_response.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_admin_add_form_supports_phone_only_users(self):
        admin = User.objects.create_superuser(
            phone="+242061234569",
            password="SecureStrongPass!927",
        )
        self.client.force_login(admin)

        response = self.client.get("/admin/accounts/user/add/")

        self.assertEqual(response.status_code, 200)

    def test_registration_refreshes_csrf_token_for_following_requests(self):
        client = Client(enforce_csrf_checks=True)
        csrf_token = client.get("/api/csrf/").json()["csrfToken"]

        registration = client.post(
            "/api/auth/register/",
            data=json.dumps(
                {
                    "phone": "+242061234567",
                    "password": "SecureStrongPass!927",
                }
            ),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=csrf_token,
        )
        self.assertEqual(registration.status_code, 201)

        refreshed_token = client.get("/api/csrf/").json()["csrfToken"]
        logout_response = client.post(
            "/api/auth/logout/",
            data="{}",
            content_type="application/json",
            HTTP_X_CSRFTOKEN=refreshed_token,
        )
        self.assertEqual(logout_response.status_code, 200)

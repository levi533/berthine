import json
import uuid

from django.test import TestCase, override_settings

from accounts.models import User

from .models import Transfer


class FakeTransferProvider:
    calls = []

    def send_transfer(self, transfer, idempotency_key):
        self.calls.append((transfer.pk, idempotency_key))
        return {
            "status": Transfer.Status.COMPLETED,
            "provider_reference": "provider-123",
        }


class TransferAPITests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            phone="+242061234567",
            password="SecureStrongPass!927",
        )
        self.client.force_login(self.user)
        self.idempotency_key = str(uuid.uuid4())
        FakeTransferProvider.calls = []
        self.payload = {
            "source_currency": "EUR",
            "destination_currency": "XAF",
            "amount": "100",
            "recipient_name": "Awa Client",
            "recipient_phone": "+242061234568",
            "idempotency_key": self.idempotency_key,
        }

    def post_json(self, path, data):
        return self.client.post(
            path,
            data=json.dumps(data),
            content_type="application/json",
        )

    def test_quote_returns_indicative_amounts(self):
        response = self.client.get(
            "/api/transfers/quote/",
            {"source": "EUR", "destination": "XAF", "amount": "100"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["indicative"])
        self.assertEqual(response.json()["fee"], "1.50")

    @override_settings(TRANSFER_PROVIDER_CLASS="")
    def test_no_provider_never_creates_or_claims_a_transfer(self):
        response = self.post_json("/api/transfers/", self.payload)

        self.assertEqual(response.status_code, 503)
        self.assertIn("Aucun argent n'a été envoyé", response.json()["error"])
        self.assertEqual(Transfer.objects.count(), 0)

    @override_settings(TRANSFER_PROVIDER_CLASS="transfers.tests.FakeTransferProvider")
    def test_transfer_creation_is_idempotent(self):
        first_response = self.post_json("/api/transfers/", self.payload)
        second_response = self.post_json("/api/transfers/", self.payload)

        self.assertEqual(first_response.status_code, 201)
        self.assertEqual(second_response.status_code, 200)
        self.assertEqual(
            first_response.json()["transfer"]["id"],
            second_response.json()["transfer"]["id"],
        )
        self.assertEqual(Transfer.objects.count(), 1)
        self.assertEqual(len(FakeTransferProvider.calls), 1)
        history = self.client.get("/api/transfers/history/").json()["transfers"]
        self.assertTrue(history[0]["can_review"])

    @override_settings(TRANSFER_PROVIDER_CLASS="transfers.tests.FakeTransferProvider")
    def test_idempotency_key_cannot_be_reused_for_different_transfer(self):
        self.post_json("/api/transfers/", self.payload)
        changed_payload = {**self.payload, "recipient_name": "Different Recipient"}

        response = self.post_json("/api/transfers/", changed_payload)

        self.assertEqual(response.status_code, 409)
        self.assertEqual(Transfer.objects.count(), 1)
        self.assertEqual(len(FakeTransferProvider.calls), 1)

    def test_history_is_private(self):
        self.assertEqual(self.client.get("/api/transfers/history/").status_code, 200)
        self.client.logout()
        response = self.client.get("/api/transfers/history/")
        self.assertEqual(response.status_code, 401)

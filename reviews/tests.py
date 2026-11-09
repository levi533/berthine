import json
import uuid

from django.test import TestCase

from accounts.models import User
from transfers.models import Transfer

from .models import Review


class ReviewAPITests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            phone="+242061234567",
            password="SecureStrongPass!927",
        )
        self.client.force_login(self.user)
        self.transfer = Transfer.objects.create(
            idempotency_key=uuid.uuid4(),
            user=self.user,
            source_currency="EUR",
            destination_currency="XAF",
            source_amount="100.00",
            fee="1.50",
            exchange_rate="655.957000",
            receive_amount="64607",
            recipient_name="Awa Client",
            recipient_phone="+242061234568",
            status=Transfer.Status.COMPLETED,
        )

    def post_json(self, path, data):
        return self.client.post(
            path,
            data=json.dumps(data),
            content_type="application/json",
        )

    def test_submitted_review_waits_for_moderation(self):
        response = self.post_json(
            "/api/reviews/",
            {
                "transfer_id": str(self.transfer.pk),
                "rating": 5,
                "text": "Service clair et simple.",
            },
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["status"], "pending_moderation")
        self.assertEqual(Review.objects.get().status, Review.Status.PENDING)
        self.assertEqual(self.client.get("/api/reviews/").json()["reviews"], [])

    def test_only_approved_reviews_are_public(self):
        review = Review.objects.create(
            transfer=self.transfer,
            rating=5,
            text="Avis approuvé.",
            status=Review.Status.APPROVED,
        )

        response = self.client.get("/api/reviews/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["reviews"][0]["id"], review.pk)
        self.assertEqual(response.json()["reviews"][0]["text"], "Avis approuvé.")

    def test_review_requires_completed_transfer_owned_by_user(self):
        self.transfer.status = Transfer.Status.PROCESSING
        self.transfer.save(update_fields=("status",))

        response = self.post_json(
            "/api/reviews/",
            {
                "transfer_id": str(self.transfer.pk),
                "rating": 5,
                "text": "Pas encore terminé.",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(Review.objects.count(), 0)

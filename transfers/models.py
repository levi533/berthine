import uuid

from django.conf import settings
from django.db import models


class Transfer(models.Model):
    class Status(models.TextChoices):
        PROCESSING = "processing", "En cours"
        COMPLETED = "completed", "Terminée"
        FAILED = "failed", "Échouée"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    idempotency_key = models.UUIDField(unique=True, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="transfers",
    )
    source_currency = models.CharField(max_length=3)
    destination_currency = models.CharField(max_length=3)
    source_amount = models.DecimalField(max_digits=18, decimal_places=2)
    fee = models.DecimalField(max_digits=18, decimal_places=2)
    exchange_rate = models.DecimalField(max_digits=20, decimal_places=6)
    receive_amount = models.DecimalField(max_digits=18, decimal_places=2)
    recipient_name = models.CharField(max_length=120)
    recipient_phone = models.CharField(max_length=16)
    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.PROCESSING,
    )
    provider_reference = models.CharField(max_length=120, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.source_amount} {self.source_currency} → {self.recipient_phone}"

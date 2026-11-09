from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from transfers.models import Transfer


class Review(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "En attente"
        APPROVED = "approved", "Publié"
        REJECTED = "rejected", "Refusé"

    transfer = models.OneToOneField(
        Transfer,
        on_delete=models.PROTECT,
        related_name="review",
    )
    rating = models.PositiveSmallIntegerField(
        validators=(MinValueValidator(1), MaxValueValidator(5)),
    )
    text = models.TextField(max_length=1000)
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.PENDING,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.rating}/5 — transfert {self.transfer_id}"

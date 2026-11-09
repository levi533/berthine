from django.contrib import admin

from .models import Transfer


@admin.register(Transfer)
class TransferAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "source_amount",
        "source_currency",
        "destination_currency",
        "status",
        "created_at",
    )
    list_filter = ("status", "source_currency", "destination_currency", "created_at")
    search_fields = ("id", "user__phone", "recipient_phone", "provider_reference")
    readonly_fields = ("id", "idempotency_key", "created_at", "updated_at")

    def has_add_permission(self, request):
        return False

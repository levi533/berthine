from django.contrib import admin

from .models import Review


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("id", "transfer", "rating", "status", "created_at")
    list_filter = ("status", "rating", "created_at")
    search_fields = ("transfer__user__phone", "transfer__recipient_phone", "text")
    list_editable = ("status",)
    readonly_fields = ("created_at", "updated_at")

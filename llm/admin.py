from django.contrib import admin

from .models import LlmCallLog


@admin.register(LlmCallLog)
class LlmCallLogAdmin(admin.ModelAdmin):
    list_display = ("engagement", "provider", "purpose", "status", "duration_ms", "created_at")
    list_filter = ("status", "provider", "purpose")

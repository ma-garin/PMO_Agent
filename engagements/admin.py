from django.contrib import admin

from .models import ActivityLog, Engagement


@admin.register(Engagement)
class EngagementAdmin(admin.ModelAdmin):
    list_display = ("name", "status", "progress", "llm_provider", "owner", "updated_at")
    list_filter = ("status", "llm_provider")
    search_fields = ("name",)


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ("engagement", "actor", "message", "created_at")

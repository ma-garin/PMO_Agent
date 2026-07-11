from django.contrib import admin

from .models import Notification, StagnationRule, SyncRun, Ticket, TicketSource


@admin.register(TicketSource)
class TicketSourceAdmin(admin.ModelAdmin):
    list_display = ("name", "kind", "engagement", "is_active", "last_synced_at")
    list_filter = ("kind", "is_active")


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = (
        "external_id",
        "summary",
        "source",
        "status",
        "is_done",
        "due_date",
    )
    list_filter = ("is_done", "source__engagement")
    search_fields = ("external_id", "summary")


@admin.register(SyncRun)
class SyncRunAdmin(admin.ModelAdmin):
    list_display = ("source", "status", "tickets_synced", "started_at", "finished_at")
    list_filter = ("status",)


@admin.register(StagnationRule)
class StagnationRuleAdmin(admin.ModelAdmin):
    list_display = ("engagement", "stale_after_days", "notify_on_overdue")


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("engagement", "ticket", "kind", "is_read", "created_at")
    list_filter = ("kind", "is_read")

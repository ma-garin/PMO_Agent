from django.contrib import admin

from .models import GeneralNotification, ImprovementAction, RiskItem


@admin.register(RiskItem)
class RiskItemAdmin(admin.ModelAdmin):
    list_display = ("title", "engagement", "probability", "impact", "status")
    list_filter = ("status",)


@admin.register(ImprovementAction)
class ImprovementActionAdmin(admin.ModelAdmin):
    list_display = ("title", "engagement", "status", "due_date")
    list_filter = ("status",)


@admin.register(GeneralNotification)
class GeneralNotificationAdmin(admin.ModelAdmin):
    list_display = ("engagement", "kind", "is_read", "created_at")
    list_filter = ("kind", "is_read")

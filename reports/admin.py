from django.contrib import admin

from .models import Report, ReportTemplate


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ("title", "engagement", "status", "period_start", "period_end", "created_at")
    list_filter = ("status",)


@admin.register(ReportTemplate)
class ReportTemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "is_default", "updated_at")

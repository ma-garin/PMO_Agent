from django.contrib import admin

from .models import Dependency, Schedule, WorkItem


@admin.register(Schedule)
class ScheduleAdmin(admin.ModelAdmin):
    list_display = ("engagement", "status_date", "updated_at")


@admin.register(WorkItem)
class WorkItemAdmin(admin.ModelAdmin):
    list_display = ("wbs_code", "title", "schedule", "start_date", "finish_date", "progress")
    list_filter = ("schedule", "kind", "status")


@admin.register(Dependency)
class DependencyAdmin(admin.ModelAdmin):
    list_display = ("predecessor", "successor", "lag_days")

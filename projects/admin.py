from django.contrib import admin

from .models import ActivityLog, Project, Task


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("name", "status", "progress", "owner", "updated_at")
    list_filter = ("status",)
    search_fields = ("name",)


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ("title", "project", "assignee", "priority", "status", "due_date")
    list_filter = ("status", "priority", "project")
    search_fields = ("title",)


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ("project", "actor", "message", "created_at")

from django.contrib import admin

from .models import TpiAnswer, TpiAssessment, TpiCheckpoint, TpiKeyArea


@admin.register(TpiKeyArea)
class TpiKeyAreaAdmin(admin.ModelAdmin):
    list_display = ("name", "order", "is_active")


@admin.register(TpiCheckpoint)
class TpiCheckpointAdmin(admin.ModelAdmin):
    list_display = ("text", "key_area", "level", "order")
    list_filter = ("key_area", "level")


@admin.register(TpiAssessment)
class TpiAssessmentAdmin(admin.ModelAdmin):
    list_display = ("title", "engagement", "status", "created_at")
    list_filter = ("status",)


@admin.register(TpiAnswer)
class TpiAnswerAdmin(admin.ModelAdmin):
    list_display = ("assessment", "checkpoint", "result")
    list_filter = ("result",)

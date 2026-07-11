from django.contrib import admin

from .models import QualityGate, TestPlan, TestProgressEntry


@admin.register(TestPlan)
class TestPlanAdmin(admin.ModelAdmin):
    list_display = ("title", "engagement", "kind", "status")
    list_filter = ("kind", "status")


@admin.register(TestProgressEntry)
class TestProgressEntryAdmin(admin.ModelAdmin):
    list_display = ("engagement", "test_level", "date", "planned_cases", "executed_cases", "passed_cases")
    list_filter = ("test_level",)


@admin.register(QualityGate)
class QualityGateAdmin(admin.ModelAdmin):
    list_display = ("name", "engagement", "verdict", "created_at")
    list_filter = ("verdict",)

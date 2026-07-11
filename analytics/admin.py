from django.contrib import admin

from .models import OdcClassification


@admin.register(OdcClassification)
class OdcClassificationAdmin(admin.ModelAdmin):
    list_display = (
        "ticket",
        "defect_type",
        "trigger",
        "activity",
        "impact",
        "source",
        "status",
    )
    list_filter = ("status", "source", "defect_type", "activity")

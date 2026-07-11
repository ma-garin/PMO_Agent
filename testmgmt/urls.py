from django.urls import path

from . import views

app_name = "testmgmt"

urlpatterns = [
    path("plans/", views.plan_list, name="plans"),
    path("plans/new/", views.plan_create, name="plan_create"),
    path("plans/<int:pk>/", views.plan_edit, name="plan_edit"),
    path("progress/", views.progress_view, name="progress"),
    path("progress/entry/", views.progress_entry_create, name="progress_entry_create"),
    path("progress/import/", views.progress_csv_import, name="progress_import"),
    path("progress/export.csv", views.progress_export_csv, name="progress_export_csv"),
    path("gates/", views.gate_list, name="gates"),
    path("gates/new/", views.gate_create, name="gate_create"),
    path("gates/<int:pk>/", views.gate_detail, name="gate_detail"),
]

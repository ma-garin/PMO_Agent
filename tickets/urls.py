from django.urls import path

from . import views

app_name = "tickets"

urlpatterns = [
    path("", views.ticket_list, name="list"),
    path("new/", views.ticket_create, name="create"),
    path("export.csv", views.ticket_export_csv, name="export_csv"),
    path("sources/", views.source_settings, name="source_settings"),
    path("<int:pk>/", views.ticket_detail, name="detail"),
    path("<int:pk>/edit/", views.ticket_edit, name="edit"),
    path("<int:pk>/delete/", views.ticket_delete, name="delete"),
    path("sources/<int:pk>/sync/", views.sync_source_now, name="sync_source"),
    path(
        "notifications/mark-read/",
        views.mark_notifications_read,
        name="mark_notifications_read",
    ),
]

from django.urls import path

from . import views

app_name = "analytics"

urlpatterns = [
    path("", views.analysis, name="analysis"),
    path("classify/<int:ticket_id>/", views.classify_ticket, name="classify"),
    path("settings/", views.update_settings, name="update_settings"),
]

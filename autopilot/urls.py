from django.urls import path

from . import views

app_name = "autopilot"

urlpatterns = [
    path("", views.queue, name="queue"),
    path("<int:pk>/approve/", views.approve, name="approve"),
    path("<int:pk>/reject/", views.reject, name="reject"),
    path("history/", views.history, name="history"),
    path("settings/", views.settings_view, name="settings"),
    path("run-now/", views.run_now, name="run_now"),
]

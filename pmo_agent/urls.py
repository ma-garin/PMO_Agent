from django.urls import path

from . import views

app_name = "pmo_agent"

urlpatterns = [
    path("", views.home, name="home"),
    path("api/tasks/", views.tasks_api, name="tasks_api"),
]

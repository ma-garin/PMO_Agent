from django.urls import path

from . import views

app_name = "pmo_agent"

urlpatterns = [
    path("", views.home, name="home"),
    path("api/tasks/", views.tasks_api, name="tasks_api"),
    path("api/stores/<str:kind>/", views.stores_api, name="stores_api"),
    path("api/ai/run/", views.ai_run, name="ai_run"),
]

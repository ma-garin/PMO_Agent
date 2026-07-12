from django.urls import path

from . import views

app_name = "planning"

urlpatterns = [
    path("", views.gantt, name="gantt"),
]

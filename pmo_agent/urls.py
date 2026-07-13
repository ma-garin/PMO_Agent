from django.urls import path

from . import views

app_name = "pmo_agent"

urlpatterns = [
    path("", views.home, name="home"),
]

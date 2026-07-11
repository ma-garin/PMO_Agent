from django.urls import path

from . import views

app_name = "copilot"

urlpatterns = [
    path("", views.home, name="home"),
    path("threads/new/", views.new_thread, name="new_thread"),
    path("threads/<int:pk>/", views.thread, name="thread"),
    path("threads/<int:pk>/send/", views.send, name="send"),
]

from django.urls import path

from . import views

app_name = "projects"

urlpatterns = [
    path("", views.ProjectSelectView.as_view(), name="select"),
    path("new/", views.ProjectCreateView.as_view(), name="create"),
    path("<int:pk>/enter/", views.select_project, name="enter"),
]

from django.urls import path

from . import views

app_name = "planning"

urlpatterns = [
    path("", views.gantt, name="gantt"),
    path("tasks/new/", views.work_item_create, name="work_item_create"),
    path("tasks/<int:pk>/edit/", views.work_item_edit, name="work_item_edit"),
    path("tasks/<int:pk>/delete/", views.work_item_delete, name="work_item_delete"),
]

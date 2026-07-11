from django.urls import path

from . import views

app_name = "members"

urlpatterns = [
    path("", views.member_list, name="list"),
    path("alias/new/", views.alias_create, name="alias_create"),
    path("alias/<int:pk>/delete/", views.alias_delete, name="alias_delete"),
]

from django.urls import path

from . import views

app_name = "risks"

urlpatterns = [
    path("", views.risk_list, name="list"),
    path("new/", views.risk_create, name="create"),
    path("<int:pk>/edit/", views.risk_edit, name="edit"),
    path("<int:pk>/status/", views.risk_change_status, name="change_status"),
    path("suggest/", views.risk_suggest, name="suggest"),
    path("proposals/<int:index>/adopt/", views.risk_adopt_proposal, name="adopt_proposal"),
    path("actions/", views.action_list, name="actions"),
    path("actions/new/", views.action_create, name="action_create"),
    path("actions/<int:pk>/status/", views.action_change_status, name="action_status"),
]

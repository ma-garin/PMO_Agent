from django.urls import path

from . import views

app_name = "reports"

urlpatterns = [
    path("", views.report_list, name="list"),
    path("create/", views.report_create, name="create"),
    path("<int:pk>/", views.report_edit, name="edit"),
    path("<int:pk>/print/", views.report_print, name="print"),
]

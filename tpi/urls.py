from django.urls import path

from . import views

app_name = "tpi"

urlpatterns = [
    path("", views.assessment_list, name="list"),
    path("<int:pk>/", views.assessment_detail, name="detail"),
    path("<int:pk>/answer/<int:key_area_pk>/", views.answer_key_area, name="answer"),
    path("<int:pk>/finalize/", views.finalize, name="finalize"),
    path("<int:pk>/suggest/", views.suggest, name="suggest"),
]

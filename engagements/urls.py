from django.urls import path

from . import views

app_name = "engagements"

urlpatterns = [
    path("", views.EngagementSelectView.as_view(), name="select"),
    path("new/", views.EngagementCreateView.as_view(), name="create"),
    path("<int:pk>/enter/", views.enter_engagement, name="enter"),
    path("settings/llm/", views.llm_settings, name="llm_settings"),
]

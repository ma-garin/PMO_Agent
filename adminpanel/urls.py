from django.urls import path

from . import views

app_name = "adminpanel"

urlpatterns = [
    path("", views.home, name="home"),
    path("engagements/", views.engagements, name="engagements"),
    path("engagements/<int:pk>/edit/", views.engagement_edit, name="engagement_edit"),
    path("engagements/<int:pk>/delete/", views.engagement_delete, name="engagement_delete"),
    path("users/", views.users, name="users"),
    path("llm-usage/", views.llm_usage, name="llm_usage"),
    path("ai-logs/", views.ai_logs, name="ai_logs"),
    path("audit/", views.audit, name="audit"),
]

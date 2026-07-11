from django.urls import path

from . import views

app_name = "adminpanel"

urlpatterns = [
    path("", views.home, name="home"),
    path("users/", views.users, name="users"),
    path("engagements/", views.engagements, name="engagements"),
    path("engagements/<int:pk>/", views.engagement_edit, name="engagement_edit"),
    path("tokens/", views.tokens, name="tokens"),
    path("llm-logs/", views.llm_logs, name="llm_logs"),
]

"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

from dashboard import views as dashboard_views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("search/", dashboard_views.search_results, name="search"),
    path("accounts/", include("accounts.urls")),
    path("engagements/", include("engagements.urls")),
    path("dashboard/", include("dashboard.urls")),
    path("tickets/", include("tickets.urls")),
    path("analytics/", include("analytics.urls")),
    path("manage/", include("adminpanel.urls")),
    path("copilot/", include("copilot.urls")),
    path("reports/", include("reports.urls")),
    path("knowledge/", include("knowledge.urls")),
    path("tpi/", include("tpi.urls")),
    path("risks/", include("risks.urls")),
    path("testmgmt/", include("testmgmt.urls")),
    path("members/", include("members.urls")),
    path("autopilot/", include("autopilot.urls")),
    path("", RedirectView.as_view(pattern_name="engagements:select", permanent=False)),
]

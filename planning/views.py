from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from engagements.models import Engagement

from .models import Schedule
from .services import gantt_chart_data


def _current_engagement(request):
    engagement_id = request.session.get("current_engagement_id")
    if not engagement_id:
        return None
    return get_object_or_404(Engagement, pk=engagement_id)


@login_required
def gantt(request):
    engagement = _current_engagement(request)
    if engagement is None:
        return redirect("engagements:select")

    schedule = Schedule.objects.filter(engagement=engagement).first()
    chart = gantt_chart_data(schedule) if schedule else None
    items = list(schedule.items.select_related("owner", "improvement_action")) if schedule else []

    context = {
        "engagement": engagement,
        "nav_active": "planning",
        "schedule": schedule,
        "chart": chart,
        "items": items,
    }
    return render(request, "planning/gantt.html", context)

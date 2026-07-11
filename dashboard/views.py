from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from engagements.models import Engagement
from tickets.models import Ticket


@login_required
def home(request):
    engagement_id = request.session.get("current_engagement_id")
    if not engagement_id:
        return redirect("engagements:select")

    engagement = get_object_or_404(Engagement, pk=engagement_id)
    today = timezone.localdate()
    week_start = today - timedelta(days=today.weekday())

    tickets = Ticket.objects.filter(source__engagement=engagement)
    today_tickets = tickets.filter(due_date=today).exclude(is_done=True)
    completed_this_week = tickets.filter(
        is_done=True, synced_at__date__gte=week_start
    )
    overdue_tickets = tickets.filter(due_date__lt=today).exclude(is_done=True)
    in_progress_tickets = tickets.exclude(is_done=True)

    total_tickets = tickets.count()
    done_tickets = tickets.filter(is_done=True).count()
    progress_percent = (
        int(done_tickets / total_tickets * 100) if total_tickets else 0
    )

    high_priority_names = ["highest", "high", "urgent", "高", "最高"]

    context = {
        "engagement": engagement,
        "today": today,
        "nav_active": "home",
        "total_tickets": total_tickets,
        "today_tasks": today_tickets.order_by("due_date")[:5],
        "today_tasks_count": today_tickets.count(),
        "today_tasks_high_count": today_tickets.filter(
            priority__iregex=r"|".join(high_priority_names)
        ).count(),
        "completed_this_week_count": completed_this_week.count(),
        "overdue_tasks_count": overdue_tickets.count(),
        "in_progress_tasks_count": in_progress_tickets.count(),
        "progress_percent": progress_percent,
        "done_tasks": done_tickets,
        "total_tasks": total_tickets,
        "activities": engagement.activities.select_related("actor")[:5],
    }
    return render(request, "dashboard/home.html", context)

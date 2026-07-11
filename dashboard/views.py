from datetime import date, timedelta

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from projects.models import Project, Task


@login_required
def home(request):
    project_id = request.session.get("current_project_id")
    if not project_id:
        return redirect("projects:select")

    project = get_object_or_404(Project, pk=project_id)
    today = date.today()
    week_start = today - timedelta(days=today.weekday())

    tasks = project.tasks.select_related("assignee")
    today_tasks = tasks.filter(due_date=today).exclude(status=Task.Status.DONE)
    completed_this_week = tasks.filter(
        status=Task.Status.DONE, updated_at__date__gte=week_start
    )
    overdue_tasks = tasks.filter(due_date__lt=today).exclude(status=Task.Status.DONE)
    in_progress_tasks = tasks.filter(status=Task.Status.IN_PROGRESS)

    total_tasks = tasks.count()
    done_tasks = tasks.filter(status=Task.Status.DONE).count()
    progress_percent = int(done_tasks / total_tasks * 100) if total_tasks else 0

    context = {
        "project": project,
        "today": today,
        "nav_active": "home",
        "today_tasks": today_tasks.order_by("due_date")[:5],
        "today_tasks_count": today_tasks.count(),
        "today_tasks_high_count": today_tasks.filter(
            priority=Task.Priority.HIGH
        ).count(),
        "completed_this_week_count": completed_this_week.count(),
        "overdue_tasks_count": overdue_tasks.count(),
        "in_progress_tasks_count": in_progress_tasks.count(),
        "progress_percent": progress_percent,
        "done_tasks": done_tasks,
        "total_tasks": total_tasks,
        "activities": project.activities.select_related("actor")[:5],
    }
    return render(request, "dashboard/home.html", context)

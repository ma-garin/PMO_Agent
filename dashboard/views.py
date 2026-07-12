from datetime import timedelta

from django.apps import apps
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from config.http_utils import parse_int
from engagements.models import Engagement
from tickets.models import Ticket

from . import services

try:
    from analytics.models import WeeklyDigest
except ImportError:
    WeeklyDigest = None

SEARCH_LIMIT = 10


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

    latest_digest = None
    if WeeklyDigest is not None:
        latest_digest = WeeklyDigest.objects.filter(engagement=engagement).first()

    context = {
        "latest_digest": latest_digest,
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


@login_required
def search_results(request):
    from django.db.models import Q

    query = request.GET.get("q", "").strip()
    groups = []

    if query:
        engagement_id = request.session.get("current_engagement_id")

        engagement_matches = Engagement.objects.filter(
            Q(owner=request.user) | Q(members=request.user), name__icontains=query
        ).distinct()[:SEARCH_LIMIT]
        if engagement_matches:
            groups.append({"label": "案件", "items": [
                {"title": e.name, "url": f"/engagements/{e.pk}/enter/"} for e in engagement_matches
            ]})

        if engagement_id:
            ticket_matches = Ticket.objects.filter(
                source__engagement_id=engagement_id
            ).filter(Q(summary__icontains=query) | Q(external_id__icontains=query))[:SEARCH_LIMIT]
            if ticket_matches:
                groups.append({"label": "チケット", "items": [
                    {"title": f"{t.external_id}: {t.summary}", "url": "/tickets/?q=" + query}
                    for t in ticket_matches
                ]})

            if apps.is_installed("testmgmt"):
                from testmgmt.models import TestPlan

                plan_matches = TestPlan.objects.filter(
                    engagement_id=engagement_id, title__icontains=query
                )[:SEARCH_LIMIT]
                if plan_matches:
                    groups.append({"label": "テスト計画", "items": [
                        {"title": p.title, "url": f"/testmgmt/plans/{p.pk}/"} for p in plan_matches
                    ]})

            if apps.is_installed("reports"):
                from reports.models import Report

                report_matches = Report.objects.filter(
                    engagement_id=engagement_id, title__icontains=query
                )[:SEARCH_LIMIT]
                if report_matches:
                    groups.append({"label": "レポート", "items": [
                        {"title": r.title, "url": f"/reports/{r.pk}/"} for r in report_matches
                    ]})

            if apps.is_installed("knowledge"):
                from django.db.models import Q as KQ

                from knowledge.models import Document

                doc_matches = Document.objects.filter(
                    KQ(engagement_id=engagement_id) | KQ(engagement__isnull=True),
                    title__icontains=query,
                )[:SEARCH_LIMIT]
                if doc_matches:
                    groups.append({"label": "ナレッジ", "items": [
                        {"title": d.title, "url": "/knowledge/"} for d in doc_matches
                    ]})

    return render(request, "dashboard/search.html", {"query": query, "groups": groups, "nav_active": ""})


@login_required
def calendar_view(request):
    engagement_id = request.session.get("current_engagement_id")
    if not engagement_id:
        return redirect("engagements:select")
    engagement = get_object_or_404(Engagement, pk=engagement_id)

    today = timezone.localdate()
    year = parse_int(request.GET.get("year"), today.year, minimum=1970, maximum=2200)
    month = parse_int(request.GET.get("month"), today.month)

    if month < 1:
        month = 12
        year -= 1
    elif month > 12:
        month = 1
        year += 1

    weeks = services.month_grid(engagement, year, month)

    prev_month = month - 1 or 12
    prev_year = year if month > 1 else year - 1
    next_month = month + 1 if month < 12 else 1
    next_year = year if month < 12 else year + 1

    context = {
        "engagement": engagement,
        "nav_active": "calendar",
        "weeks": weeks,
        "year": year,
        "month": month,
        "today": today,
        "prev_year": prev_year,
        "prev_month": prev_month,
        "next_year": next_year,
        "next_month": next_month,
    }
    return render(request, "dashboard/calendar.html", context)

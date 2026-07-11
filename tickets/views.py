from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from audit.services import record
from config.csv_utils import csv_response
from engagements.models import Engagement

from .forms import TicketSourceForm
from .models import Notification, Ticket
from .services import detect_stagnant_tickets, sync_ticket_source


def _current_engagement(request):
    engagement_id = request.session.get("current_engagement_id")
    if not engagement_id:
        return None
    return get_object_or_404(Engagement, pk=engagement_id)


@login_required
def ticket_list(request):
    engagement = _current_engagement(request)
    if engagement is None:
        return redirect("engagements:select")

    today = timezone.localdate()
    all_tickets = Ticket.objects.filter(source__engagement=engagement)

    tab = request.GET.get("tab", "all")
    tickets = all_tickets
    if tab == "in_progress":
        tickets = tickets.exclude(is_done=True)
    elif tab == "done":
        tickets = tickets.filter(is_done=True)
    elif tab == "overdue":
        tickets = tickets.filter(is_done=False, due_date__lt=today)
    elif tab == "stagnant":
        tickets = tickets.filter(notifications__kind="stagnant").distinct()

    query = request.GET.get("q", "").strip()
    if query:
        tickets = tickets.filter(summary__icontains=query)

    tickets = tickets.select_related("source")

    counts = {
        "all": all_tickets.count(),
        "in_progress": all_tickets.exclude(is_done=True).count(),
        "done": all_tickets.filter(is_done=True).count(),
        "overdue": all_tickets.filter(is_done=False, due_date__lt=today).count(),
    }

    page_size = request.GET.get("page_size", "10")
    page_size = int(page_size) if page_size.isdigit() else 10
    paginator = Paginator(tickets, page_size)
    page_obj = paginator.get_page(request.GET.get("page"))

    context = {
        "engagement": engagement,
        "nav_active": "tickets",
        "page_obj": page_obj,
        "tab": tab,
        "query": query,
        "counts": counts,
        "total_tickets": counts["all"],
        "page_size": page_size,
        "today": today,
    }
    return render(request, "tickets/list.html", context)


@login_required
def ticket_export_csv(request):
    engagement = _current_engagement(request)
    if engagement is None:
        return redirect("engagements:select")

    today = timezone.localdate()
    tickets = Ticket.objects.filter(source__engagement=engagement).select_related("source")

    tab = request.GET.get("tab", "all")
    if tab == "in_progress":
        tickets = tickets.exclude(is_done=True)
    elif tab == "done":
        tickets = tickets.filter(is_done=True)
    elif tab == "overdue":
        tickets = tickets.filter(is_done=False, due_date__lt=today)

    query = request.GET.get("q", "").strip()
    if query:
        tickets = tickets.filter(summary__icontains=query)

    header = ["チケットID", "概要", "接続元", "優先度", "担当", "期限", "状態", "完了"]
    rows = (
        [t.external_id, t.summary, t.source.get_kind_display(), t.priority, t.assignee_name,
         t.due_date or "", t.status, "完了" if t.is_done else "未完了"]
        for t in tickets
    )
    return csv_response("tickets.csv", header, rows)


@login_required
def source_settings(request):
    engagement = _current_engagement(request)
    if engagement is None:
        return redirect("engagements:select")

    if request.method == "POST":
        if not request.user.is_staff:
            messages.error(request, "この操作には管理者権限が必要です。")
            return redirect("tickets:source_settings")

        form = TicketSourceForm(request.POST)
        if form.is_valid():
            source = form.save(commit=False)
            source.engagement = engagement
            source.save()
            record(request.user, "token_create", source, detail=source.name)
            messages.success(request, "接続設定を追加しました。")
            return redirect("tickets:source_settings")
    else:
        form = TicketSourceForm()

    context = {
        "engagement": engagement,
        "nav_active": "settings",
        "settings_tab": "tickets",
        "form": form,
        "sources": engagement.ticket_sources.all(),
    }
    return render(request, "tickets/source_settings.html", context)


@login_required
def sync_source_now(request, pk):
    engagement = _current_engagement(request)
    if engagement is None:
        return redirect("engagements:select")

    source = get_object_or_404(
        engagement.ticket_sources, pk=pk
    )
    run = sync_ticket_source(source)
    if run.status == run.Status.SUCCESS:
        new_notifications = detect_stagnant_tickets(engagement)
        message = f"{source.name} を同期しました（{run.tickets_synced}件）。"
        if new_notifications:
            message += f" 新たに{len(new_notifications)}件の通知があります。"
        messages.success(request, message)
    else:
        messages.error(request, f"{source.name} の同期に失敗しました: {run.error_message}")
    return redirect("tickets:source_settings")


@login_required
def mark_notifications_read(request):
    engagement = _current_engagement(request)
    if engagement is not None and request.method == "POST":
        Notification.objects.filter(engagement=engagement, is_read=False).update(
            is_read=True
        )
    next_url = request.POST.get("next") or "tickets:list"
    return redirect(next_url)

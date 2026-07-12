from urllib.parse import urlencode
from uuid import uuid4

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.utils.http import url_has_allowed_host_and_scheme

from audit.services import record
from config.csv_utils import csv_response
from engagements.models import Engagement

from .forms import TicketSourceForm
from .models import Notification, Ticket, TicketSource
from .services import detect_stagnant_tickets, sync_ticket_source


SORT_FIELDS = {
    "summary": "summary",
    "priority": "priority",
    "assignee": "assignee_name",
    "due": "due_date",
    "status": "status",
}


def _current_engagement(request):
    engagement_id = request.session.get("current_engagement_id")
    if not engagement_id:
        return None
    return get_object_or_404(Engagement, pk=engagement_id)


def _apply_ticket_filters(request, tickets, today):
    """一覧・CSV共通の絞り込み(タブ/検索/担当/優先度/期限)を適用する。ソートは含まない。"""
    tab = request.GET.get("tab", "all")
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

    assignee = request.GET.get("assignee", "").strip()
    if assignee:
        tickets = tickets.filter(assignee_name=assignee)

    priority = request.GET.get("priority", "").strip()
    if priority:
        tickets = tickets.filter(priority=priority)

    due_from_raw = request.GET.get("due_from", "").strip()
    due_from = parse_date(due_from_raw) if due_from_raw else None
    if due_from:
        tickets = tickets.filter(due_date__gte=due_from)

    due_to_raw = request.GET.get("due_to", "").strip()
    due_to = parse_date(due_to_raw) if due_to_raw else None
    if due_to:
        tickets = tickets.filter(due_date__lte=due_to)

    return tickets


@login_required
def ticket_list(request):
    engagement = _current_engagement(request)
    if engagement is None:
        return redirect("engagements:select")

    today = timezone.localdate()
    all_tickets = Ticket.objects.filter(source__engagement=engagement)

    tickets = _apply_ticket_filters(request, all_tickets, today).select_related("source")

    tab = request.GET.get("tab", "all")
    query = request.GET.get("q", "").strip()
    assignee = request.GET.get("assignee", "").strip()
    priority = request.GET.get("priority", "").strip()
    due_from_raw = request.GET.get("due_from", "").strip()
    due_to_raw = request.GET.get("due_to", "").strip()

    sort = request.GET.get("sort", "")
    direction = "desc" if request.GET.get("dir") == "desc" else "asc"
    if sort in SORT_FIELDS:
        order = SORT_FIELDS[sort]
        tickets = tickets.order_by(("-" if direction == "desc" else "") + order)

    counts = {
        "all": all_tickets.count(),
        "in_progress": all_tickets.exclude(is_done=True).count(),
        "done": all_tickets.filter(is_done=True).count(),
        "overdue": all_tickets.filter(is_done=False, due_date__lt=today).count(),
    }

    assignee_options = list(
        all_tickets.exclude(assignee_name="").order_by("assignee_name")
        .values_list("assignee_name", flat=True).distinct()
    )
    priority_options = list(
        all_tickets.exclude(priority="").order_by("priority")
        .values_list("priority", flat=True).distinct()
    )

    page_size = request.GET.get("page_size", "10")
    page_size = int(page_size) if page_size.isdigit() else 10
    paginator = Paginator(tickets, page_size)
    page_obj = paginator.get_page(request.GET.get("page"))

    # ページ送り・ソートリンク用のクエリ文字列(pageを除く)
    filter_params = {
        k: v
        for k, v in {
            "tab": tab, "q": query, "assignee": assignee, "priority": priority,
            "due_from": due_from_raw, "due_to": due_to_raw, "page_size": str(page_size),
        }.items()
        if v
    }
    sort_query = urlencode(filter_params)
    page_query = urlencode({**filter_params, **({"sort": sort, "dir": direction} if sort in SORT_FIELDS else {})})

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
        "assignee": assignee,
        "priority": priority,
        "due_from": due_from_raw,
        "due_to": due_to_raw,
        "assignee_options": assignee_options,
        "priority_options": priority_options,
        "sort": sort if sort in SORT_FIELDS else "",
        "direction": direction,
        "sort_query": sort_query,
        "page_query": page_query,
    }
    return render(request, "tickets/list.html", context)


MANUAL_PRIORITY_CHOICES = ["高", "中", "低"]
MANUAL_STATUS_CHOICES = ["未着手", "進行中", "レビュー中", "完了"]


def _ticket_form_context(engagement, ticket=None):
    return {
        "engagement": engagement,
        "nav_active": "tickets",
        "ticket": ticket,
        "priority_choices": MANUAL_PRIORITY_CHOICES,
        "status_choices": MANUAL_STATUS_CHOICES,
        "members": engagement.members.all(),
    }


def _apply_manual_ticket_fields(request, ticket):
    ticket.summary = request.POST.get("summary", "").strip()
    ticket.description = request.POST.get("description", "")
    ticket.priority = request.POST.get("priority", "").strip()
    ticket.assignee_name = request.POST.get("assignee_name", "").strip()
    status = request.POST.get("status", "未着手").strip() or "未着手"
    ticket.status = status
    ticket.is_done = status == "完了"
    due = request.POST.get("due_date", "").strip()
    ticket.due_date = parse_date(due) if due else None
    return ticket


@login_required
def ticket_detail(request, pk):
    engagement = _current_engagement(request)
    if engagement is None:
        return redirect("engagements:select")

    ticket = get_object_or_404(
        Ticket.objects.select_related("source"), pk=pk, source__engagement=engagement
    )
    context = {
        "engagement": engagement,
        "nav_active": "tickets",
        "ticket": ticket,
        "today": timezone.localdate(),
        "transitions": ticket.status_transitions.order_by("-occurred_at")[:20],
    }
    return render(request, "tickets/detail.html", context)


@login_required
def ticket_create(request):
    engagement = _current_engagement(request)
    if engagement is None:
        return redirect("engagements:select")

    if request.method == "POST":
        if not request.POST.get("summary", "").strip():
            messages.error(request, "概要を入力してください。")
            return render(request, "tickets/form.html", _ticket_form_context(engagement))
        ticket = _apply_manual_ticket_fields(
            request,
            Ticket(
                source=TicketSource.get_internal(engagement),
                external_id=f"M-{uuid4().hex[:8].upper()}",
            ),
        )
        ticket.save()
        messages.success(request, "チケットを作成しました。")
        return redirect("tickets:detail", pk=ticket.pk)

    return render(request, "tickets/form.html", _ticket_form_context(engagement))


@login_required
def ticket_edit(request, pk):
    engagement = _current_engagement(request)
    if engagement is None:
        return redirect("engagements:select")

    ticket = get_object_or_404(
        Ticket.objects.select_related("source"), pk=pk, source__engagement=engagement
    )
    if not ticket.is_manual:
        messages.error(request, "外部連携のチケットはこのシステム上では編集できません。")
        return redirect("tickets:detail", pk=pk)

    if request.method == "POST":
        if not request.POST.get("summary", "").strip():
            messages.error(request, "概要を入力してください。")
            return render(request, "tickets/form.html", _ticket_form_context(engagement, ticket))
        _apply_manual_ticket_fields(request, ticket).save()
        messages.success(request, "チケットを更新しました。")
        return redirect("tickets:detail", pk=pk)

    return render(request, "tickets/form.html", _ticket_form_context(engagement, ticket))


@login_required
def ticket_delete(request, pk):
    engagement = _current_engagement(request)
    if engagement is None:
        return redirect("engagements:select")

    ticket = get_object_or_404(
        Ticket.objects.select_related("source"), pk=pk, source__engagement=engagement
    )
    if request.method == "POST" and ticket.is_manual:
        ticket.delete()
        messages.success(request, "チケットを削除しました。")
        return redirect("tickets:list")
    return redirect("tickets:detail", pk=pk)


@login_required
def ticket_export_csv(request):
    engagement = _current_engagement(request)
    if engagement is None:
        return redirect("engagements:select")

    today = timezone.localdate()
    base = Ticket.objects.filter(source__engagement=engagement).select_related("source")
    tickets = _apply_ticket_filters(request, base, today)

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
    # F-8(CWE-601): nextは自サイト内のパスのみ許可し、外部URLへのリダイレクトを防ぐ
    next_url = request.POST.get("next", "")
    if not url_has_allowed_host_and_scheme(
        next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        next_url = "tickets:list"
    return redirect(next_url)

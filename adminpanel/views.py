from datetime import datetime

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from accounts.decorators import admin_required
from audit.models import AuditLog
from audit.services import record
from engagements.models import Engagement
from llm.models import LlmCallLog
from llm.services import usage_summary

from .forms import AdminEngagementForm

User = get_user_model()


def _base_context(active: str) -> dict:
    return {"nav_active": "manage", "admin_active": active}


@admin_required
def home(request: HttpRequest) -> HttpResponse:
    now = timezone.localtime()
    month_logs = LlmCallLog.objects.filter(
        created_at__year=now.year, created_at__month=now.month
    )
    context = {
        **_base_context("home"),
        "engagement_count": Engagement.objects.count(),
        "active_count": Engagement.objects.filter(status="active").count(),
        "user_count": User.objects.count(),
        "staff_count": User.objects.filter(is_staff=True).count(),
        "llm_calls_month": month_logs.count(),
        "llm_fail_month": month_logs.filter(status=LlmCallLog.Status.FAILED).count(),
        "llm_chars_month": month_logs.aggregate(
            total=Sum("prompt_chars") + Sum("response_chars")
        )["total"]
        or 0,
        "audit_count": AuditLog.objects.count(),
        "recent_audit": AuditLog.objects.select_related("actor")[:8],
    }
    return render(request, "adminpanel/home.html", context)


@admin_required
def engagements(request: HttpRequest) -> HttpResponse:
    qs = Engagement.objects.select_related("owner").annotate(
        member_total=Count("members", distinct=True)
    )
    q = (request.GET.get("q") or "").strip()
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(description__icontains=q))
    status = request.GET.get("status") or ""
    if status:
        qs = qs.filter(status=status)
    qs = qs.order_by("-updated_at")
    page_obj = Paginator(qs, 20).get_page(request.GET.get("page"))
    context = {
        **_base_context("engagements"),
        "page_obj": page_obj,
        "q": q,
        "status": status,
        "status_choices": Engagement.Status.choices,
        "page_query": f"q={q}&status={status}",
    }
    return render(request, "adminpanel/engagements.html", context)


@admin_required
def engagement_edit(request: HttpRequest, pk: int) -> HttpResponse:
    engagement = get_object_or_404(Engagement, pk=pk)
    if request.method == "POST":
        form = AdminEngagementForm(request.POST, instance=engagement)
        if form.is_valid():
            form.save()
            record(request.user, "engagement_edit", engagement, detail=engagement.name)
            messages.success(request, f"案件「{engagement.name}」を更新しました。")
            return redirect("adminpanel:engagements")
    else:
        form = AdminEngagementForm(instance=engagement)
    context = {**_base_context("engagements"), "form": form, "engagement": engagement}
    return render(request, "adminpanel/engagement_edit.html", context)


@admin_required
def engagement_delete(request: HttpRequest, pk: int) -> HttpResponse:
    engagement = get_object_or_404(Engagement, pk=pk)
    if request.method == "POST":
        name = engagement.name
        record(request.user, "engagement_delete", engagement, detail=name)
        engagement.delete()
        messages.success(request, f"案件「{name}」を削除しました。")
        return redirect("adminpanel:engagements")
    context = {**_base_context("engagements"), "engagement": engagement}
    return render(request, "adminpanel/engagement_delete.html", context)


@admin_required
def users(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        target = get_object_or_404(User, pk=request.POST.get("user_id"))
        field = request.POST.get("field")
        if target.pk == request.user.pk:
            messages.error(request, "自分自身の権限は変更できません。")
        elif field in ("is_active", "is_staff"):
            setattr(target, field, not getattr(target, field))
            target.save(update_fields=[field])
            record(request.user, "user_edit", target, detail=f"{field}={getattr(target, field)}")
            messages.success(request, f"{target.username} の {field} を更新しました。")
        return redirect("adminpanel:users")
    qs = User.objects.order_by("username")
    page_obj = Paginator(qs, 25).get_page(request.GET.get("page"))
    return render(request, "adminpanel/users.html", {**_base_context("users"), "page_obj": page_obj})


def _month_from_request(request: HttpRequest) -> tuple[int, int]:
    now = timezone.localtime()
    raw = request.GET.get("month") or f"{now.year}-{now.month:02d}"
    try:
        dt = datetime.strptime(raw, "%Y-%m")
        return dt.year, dt.month
    except ValueError:
        return now.year, now.month


@admin_required
def llm_usage(request: HttpRequest) -> HttpResponse:
    year, month = _month_from_request(request)
    rows = usage_summary(year, month)
    totals = {
        "calls": sum(r["call_count"] for r in rows),
        "chars": sum(r["total_chars"] or 0 for r in rows),
        "failures": sum(r["failure_count"] for r in rows),
        "warnings": sum(1 for r in rows if r.get("warning")),
    }
    context = {
        **_base_context("llm_usage"),
        "rows": rows,
        "totals": totals,
        "month_value": f"{year}-{month:02d}",
    }
    return render(request, "adminpanel/llm_usage.html", context)


@admin_required
def ai_logs(request: HttpRequest) -> HttpResponse:
    qs = LlmCallLog.objects.select_related("engagement", "created_by").order_by("-created_at")
    status = request.GET.get("status") or ""
    if status in (LlmCallLog.Status.SUCCESS, LlmCallLog.Status.FAILED):
        qs = qs.filter(status=status)
    page_obj = Paginator(qs, 30).get_page(request.GET.get("page"))
    context = {
        **_base_context("ai_logs"),
        "page_obj": page_obj,
        "status": status,
        "page_query": f"status={status}",
    }
    return render(request, "adminpanel/ai_logs.html", context)


@admin_required
def audit(request: HttpRequest) -> HttpResponse:
    qs = AuditLog.objects.select_related("actor").order_by("-created_at")
    action = request.GET.get("action") or ""
    if action:
        qs = qs.filter(action=action)
    actor = request.GET.get("actor") or ""
    if actor:
        qs = qs.filter(actor__username__icontains=actor)
    page_obj = Paginator(qs, 40).get_page(request.GET.get("page"))
    actions = (
        AuditLog.objects.values_list("action", flat=True).distinct().order_by("action")
    )
    context = {
        **_base_context("audit"),
        "page_obj": page_obj,
        "action": action,
        "actor": actor,
        "actions": actions,
        "page_query": f"action={action}&actor={actor}",
    }
    return render(request, "adminpanel/audit.html", context)

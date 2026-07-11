import markdown
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from engagements.models import Engagement
from llm.providers.base import LlmError

from .models import Report
from .services import generate_draft


def _current_engagement(request):
    engagement_id = request.session.get("current_engagement_id")
    if not engagement_id:
        return None
    return get_object_or_404(Engagement, pk=engagement_id)


@login_required
def report_list(request):
    engagement = _current_engagement(request)
    if engagement is None:
        return redirect("engagements:select")

    context = {
        "engagement": engagement,
        "nav_active": "reports",
        "reports": engagement.reports.all(),
        "today": timezone.localdate(),
    }
    return render(request, "reports/list.html", context)


@login_required
def report_create(request):
    engagement = _current_engagement(request)
    if engagement is None:
        return redirect("engagements:select")

    if request.method != "POST":
        return redirect("reports:list")

    title = request.POST.get("title", "").strip() or "品質状況報告書"
    period_start = request.POST.get("period_start")
    period_end = request.POST.get("period_end")

    report = Report.objects.create(
        engagement=engagement,
        title=title,
        period_start=period_start,
        period_end=period_end,
        created_by=request.user,
    )
    try:
        report.body = generate_draft(engagement, period_start, period_end, user=request.user)
        report.save(update_fields=["body"])
    except LlmError as exc:
        messages.error(request, f"AIドラフト生成に失敗しました: {exc}")

    return redirect("reports:edit", pk=report.pk)


@login_required
def report_edit(request, pk):
    engagement = _current_engagement(request)
    if engagement is None:
        return redirect("engagements:select")

    report = get_object_or_404(Report, pk=pk, engagement=engagement)

    if request.method == "POST":
        if report.status == Report.Status.APPROVED:
            messages.error(request, "承認済みの報告書は編集できません。")
            return redirect("reports:edit", pk=pk)

        action = request.POST.get("action")
        if action == "approve":
            report.status = Report.Status.APPROVED
            report.save(update_fields=["status"])
            messages.success(request, "報告書を承認しました。")
        else:
            report.body = request.POST.get("body", "")
            report.save(update_fields=["body"])
            messages.success(request, "保存しました。")
        return redirect("reports:edit", pk=pk)

    context = {
        "engagement": engagement,
        "nav_active": "reports",
        "report": report,
        "preview_html": markdown.markdown(report.body, extensions=["tables"]),
    }
    return render(request, "reports/edit.html", context)


@login_required
def report_print(request, pk):
    engagement = _current_engagement(request)
    if engagement is None:
        return redirect("engagements:select")

    report = get_object_or_404(Report, pk=pk, engagement=engagement)
    context = {
        "engagement": engagement,
        "report": report,
        "body_html": markdown.markdown(report.body, extensions=["tables"]),
    }
    return render(request, "reports/print.html", context)

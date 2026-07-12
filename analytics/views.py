from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from audit.services import record
from config.csv_utils import csv_response
from engagements.models import Engagement

from llm.services import LlmError

from . import services
from .llm_suggest import suggest_classification
from .models import OdcClassification


def _current_engagement(request):
    engagement_id = request.session.get("current_engagement_id")
    if not engagement_id:
        return None
    return get_object_or_404(Engagement, pk=engagement_id)


@login_required
def analysis(request):
    engagement = _current_engagement(request)
    if engagement is None:
        return redirect("engagements:select")

    defects = (
        services.get_defects(engagement)
        .select_related("source", "odc_classification")
        .order_by("is_done", "-source_updated_at")[:50]
    )
    series = services.convergence_series(engagement)
    monthly_trend = services.monthly_odc_trend(engagement)
    monthly_bars = services.monthly_odc_bars(monthly_trend)
    monthly_max = max((b["total"] for b in monthly_bars), default=0)

    context = {
        "engagement": engagement,
        "nav_active": "analytics",
        "today": timezone.localdate(),
        "summary": services.summarize_defects(engagement),
        "reopen": services.reopen_stats(engagement),
        "series": series,
        "svg": services.convergence_svg_points(series),
        "monthly_bars": monthly_bars,
        "monthly_max": monthly_max,
        "monthly_half": round(monthly_max / 2),
        "monthly_defect_types": monthly_trend["defect_types"],
        "odc": services.odc_distribution(engagement),
        "defects": defects,
        "defect_type_choices": OdcClassification.DefectType.choices,
        "trigger_choices": OdcClassification.Trigger.choices,
        "activity_choices": OdcClassification.Activity.choices,
        "impact_choices": OdcClassification.Impact.choices,
        "defect_type_values": ", ".join(services.defect_type_values(engagement)),
    }
    return render(request, "analytics/analysis.html", context)


@require_POST
@login_required
def classify_ticket(request, ticket_id):
    engagement = _current_engagement(request)
    if engagement is None:
        return redirect("engagements:select")

    ticket = get_object_or_404(
        services.get_defects(engagement), pk=ticket_id
    )
    classification, _ = OdcClassification.objects.get_or_create(ticket=ticket)
    classification.defect_type = request.POST.get("defect_type", "")
    classification.trigger = request.POST.get("trigger", "")
    classification.activity = request.POST.get("activity", "")
    classification.impact = request.POST.get("impact", "")
    classification.source = OdcClassification.Source.MANUAL
    classification.status = OdcClassification.Status.CONFIRMED
    classification.classified_by = request.user
    classification.save()
    record(request.user, "odc_confirm", classification, detail=ticket.external_id)
    messages.success(request, f"{ticket.external_id} のODC分類を確定しました。")
    return redirect("analytics:analysis")


@require_POST
@login_required
def suggest_bulk(request):
    engagement = _current_engagement(request)
    if engagement is None:
        return redirect("engagements:select")

    targets = (
        services.get_defects(engagement)
        .exclude(odc_classification__status=OdcClassification.Status.CONFIRMED)
        .order_by("source_created_at")[:10]
    )
    succeeded = 0
    failed = 0
    for ticket in targets:
        try:
            suggest_classification(ticket, user=request.user)
            succeeded += 1
        except LlmError:
            failed += 1

    if succeeded:
        messages.success(request, f"{succeeded}件のAI推定を作成しました。")
    if failed:
        messages.error(request, f"{failed}件はLLM呼び出しに失敗しました。")
    if not succeeded and not failed:
        messages.info(request, "対象の欠陥がありません。")
    return redirect("analytics:analysis")


@login_required
def export_odc_csv(request):
    engagement = _current_engagement(request)
    if engagement is None:
        return redirect("engagements:select")

    confirmed = OdcClassification.objects.filter(
        ticket__in=services.get_defects(engagement), status=OdcClassification.Status.CONFIRMED
    ).select_related("ticket")

    header = ["チケットID", "概要", "欠陥タイプ", "トリガー", "検出アクティビティ", "影響度"]
    rows = (
        [c.ticket.external_id, c.ticket.summary, c.get_defect_type_display(),
         c.get_trigger_display(), c.get_activity_display(), c.get_impact_display()]
        for c in confirmed
    )
    return csv_response("odc_classifications.csv", header, rows)


@require_POST
@login_required
def update_settings(request):
    engagement = _current_engagement(request)
    if engagement is None:
        return redirect("engagements:select")

    raw_types = request.POST.get("defect_ticket_types", "")
    engagement.defect_ticket_types = [
        value.strip() for value in raw_types.split(",") if value.strip()
    ]
    engagement.size_metric_name = request.POST.get("size_metric_name", "").strip()
    raw_size = request.POST.get("size_metric_value", "").strip()
    engagement.size_metric_value = raw_size if raw_size else None
    engagement.save(
        update_fields=["defect_ticket_types", "size_metric_name", "size_metric_value"]
    )
    messages.success(request, "分析設定を更新しました。")
    return redirect("analytics:analysis")

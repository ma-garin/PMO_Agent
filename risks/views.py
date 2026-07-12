from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.dateparse import parse_date

from config.http_utils import parse_int
from engagements.models import Engagement

from . import services
from .models import HIGH_SCORE_THRESHOLD, MEDIUM_SCORE_THRESHOLD, ImprovementAction, RiskItem


def _current_engagement(request):
    engagement_id = request.session.get("current_engagement_id")
    if not engagement_id:
        return None
    return get_object_or_404(Engagement, pk=engagement_id)


@login_required
def risk_list(request):
    engagement = _current_engagement(request)
    if engagement is None:
        return redirect("engagements:select")

    probability = request.GET.get("p")
    impact = request.GET.get("i")
    risks = RiskItem.objects.filter(engagement=engagement)
    if probability:
        risks = risks.filter(probability=probability)
    if impact:
        risks = risks.filter(impact=impact)

    proposals = request.session.get("risk_proposals", [])
    grid = services.risk_matrix(engagement)
    matrix_rows = [
        {
            "impact": impact_value,
            "cells": [
                {
                    "probability": prob_value,
                    "impact": impact_value,
                    "count": len(grid[(prob_value, impact_value)]),
                    "severity": _cell_severity(prob_value, impact_value),
                }
                for prob_value in range(1, 6)
            ],
        }
        for impact_value in range(5, 0, -1)
    ]

    context = {
        "engagement": engagement,
        "nav_active": "risks",
        "matrix_rows": matrix_rows,
        "risks": risks,
        "filtered": bool(probability or impact),
        "proposals": proposals,
        "status_choices": RiskItem.Status.choices,
    }
    return render(request, "risks/list.html", context)


def _cell_severity(probability: int, impact: int) -> str:
    score = probability * impact
    if score >= HIGH_SCORE_THRESHOLD:
        return "high"
    if score >= MEDIUM_SCORE_THRESHOLD:
        return "medium"
    return "low"


def _form_context(engagement, risk=None):
    return {
        "engagement": engagement,
        "nav_active": "risks",
        "risk": risk,
        "members": engagement.members.all(),
        "category_choices": RiskItem.Category.choices,
        "response_choices": RiskItem.Response.choices,
    }


def _apply_risk_fields(request, engagement, risk):
    """POSTの値をRiskItemインスタンスへ反映する(create/edit共通)。"""
    risk.title = request.POST.get("title", "").strip()
    risk.description = request.POST.get("description", "")
    risk.probability = parse_int(request.POST.get("probability"), 3, minimum=1, maximum=5)
    risk.impact = parse_int(request.POST.get("impact"), 3, minimum=1, maximum=5)
    risk.measurement = request.POST.get("measurement", "")
    risk.countermeasure = request.POST.get("countermeasure", "")
    category = request.POST.get("category", "")
    risk.category = category if category in RiskItem.Category.values else ""
    strategy = request.POST.get("response_strategy", "")
    risk.response_strategy = strategy if strategy in RiskItem.Response.values else ""
    risk.trigger = request.POST.get("trigger", "").strip()
    owner_id = request.POST.get("owner") or ""
    risk.owner = engagement.members.filter(pk=owner_id).first() if owner_id else None
    due = request.POST.get("due_date") or ""
    risk.due_date = parse_date(due) if due else None
    return risk


@login_required
def risk_create(request):
    engagement = _current_engagement(request)
    if engagement is None:
        return redirect("engagements:select")

    if request.method == "POST":
        risk = _apply_risk_fields(request, engagement, RiskItem(engagement=engagement))
        risk.save()
        messages.success(request, "リスクを登録しました。")
        return redirect("risks:list")

    return render(request, "risks/form.html", _form_context(engagement))


@login_required
def risk_edit(request, pk):
    engagement = _current_engagement(request)
    if engagement is None:
        return redirect("engagements:select")

    risk = get_object_or_404(RiskItem, pk=pk, engagement=engagement)
    if request.method == "POST":
        _apply_risk_fields(request, engagement, risk).save()
        messages.success(request, "リスクを更新しました。")
        return redirect("risks:list")

    return render(request, "risks/form.html", _form_context(engagement, risk=risk))


@login_required
def risk_change_status(request, pk):
    engagement = _current_engagement(request)
    if engagement is None:
        return redirect("engagements:select")

    risk = get_object_or_404(RiskItem, pk=pk, engagement=engagement)
    if request.method == "POST":
        status = request.POST.get("status")
        if status in RiskItem.Status.values:
            risk.status = status
            risk.save(update_fields=["status"])
            messages.success(request, "状態を更新しました。")
    return redirect("risks:list")


@login_required
def risk_suggest(request):
    engagement = _current_engagement(request)
    if engagement is None:
        return redirect("engagements:select")

    if request.method == "POST":
        candidates = services.suggest_risks(engagement, user=request.user)
        request.session["risk_proposals"] = candidates
        if not candidates:
            messages.info(request, "AI候補を取得できませんでした。")
    return redirect("risks:list")


@login_required
def risk_adopt_proposal(request, index):
    engagement = _current_engagement(request)
    if engagement is None:
        return redirect("engagements:select")

    proposals = request.session.get("risk_proposals", [])
    if request.method == "POST" and 0 <= index < len(proposals):
        item = proposals.pop(index)
        RiskItem.objects.create(
            engagement=engagement,
            title=item.get("title", ""),
            description=item.get("description", ""),
            probability=item.get("probability", 3),
            impact=item.get("impact", 3),
            measurement=item.get("measurement", ""),
        )
        request.session["risk_proposals"] = proposals
        messages.success(request, "候補を採用しリスクとして登録しました。")
    return redirect("risks:list")


@login_required
def action_list(request):
    engagement = _current_engagement(request)
    if engagement is None:
        return redirect("engagements:select")

    actions = ImprovementAction.objects.filter(engagement=engagement)
    context = {
        "engagement": engagement,
        "nav_active": "risks",
        "planned": actions.filter(status=ImprovementAction.Status.PLANNED),
        "in_progress": actions.filter(status=ImprovementAction.Status.IN_PROGRESS),
        "done": actions.filter(status=ImprovementAction.Status.DONE),
    }
    return render(request, "risks/actions.html", context)


@login_required
def action_create(request):
    engagement = _current_engagement(request)
    if engagement is None:
        return redirect("engagements:select")

    if request.method == "POST":
        ImprovementAction.objects.create(
            engagement=engagement,
            title=request.POST.get("title", "").strip(),
            background=request.POST.get("background", ""),
            origin_note=request.POST.get("origin_note", ""),
            due_date=request.POST.get("due_date") or None,
        )
        messages.success(request, "改善アクションを登録しました。")
        return redirect("risks:actions")

    return render(request, "risks/action_form.html", {"engagement": engagement, "nav_active": "risks"})


@login_required
def action_change_status(request, pk):
    engagement = _current_engagement(request)
    if engagement is None:
        return redirect("engagements:select")

    action = get_object_or_404(ImprovementAction, pk=pk, engagement=engagement)
    if request.method == "POST":
        status = request.POST.get("status")
        if status in ImprovementAction.Status.values:
            previous_status = action.status
            action.status = status
            action.save(update_fields=["status"])
            from audit.services import record
            from .services import sync_roadmap_progress

            sync_roadmap_progress(engagement)
            if previous_status != status:
                record(
                    request.user,
                    "improvement_action_status_change",
                    action,
                    detail=f"{previous_status} -> {status}",
                )
    return redirect("risks:actions")

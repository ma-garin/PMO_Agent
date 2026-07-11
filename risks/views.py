from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

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


@login_required
def risk_create(request):
    engagement = _current_engagement(request)
    if engagement is None:
        return redirect("engagements:select")

    if request.method == "POST":
        RiskItem.objects.create(
            engagement=engagement,
            title=request.POST.get("title", "").strip(),
            description=request.POST.get("description", ""),
            probability=int(request.POST.get("probability", 3)),
            impact=int(request.POST.get("impact", 3)),
            measurement=request.POST.get("measurement", ""),
            countermeasure=request.POST.get("countermeasure", ""),
        )
        messages.success(request, "リスクを登録しました。")
        return redirect("risks:list")

    return render(request, "risks/form.html", {"engagement": engagement, "nav_active": "risks"})


@login_required
def risk_edit(request, pk):
    engagement = _current_engagement(request)
    if engagement is None:
        return redirect("engagements:select")

    risk = get_object_or_404(RiskItem, pk=pk, engagement=engagement)
    if request.method == "POST":
        risk.title = request.POST.get("title", "").strip()
        risk.description = request.POST.get("description", "")
        risk.probability = int(request.POST.get("probability", 3))
        risk.impact = int(request.POST.get("impact", 3))
        risk.measurement = request.POST.get("measurement", "")
        risk.countermeasure = request.POST.get("countermeasure", "")
        risk.save()
        messages.success(request, "リスクを更新しました。")
        return redirect("risks:list")

    return render(
        request, "risks/form.html", {"engagement": engagement, "nav_active": "risks", "risk": risk}
    )


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
            action.status = status
            action.save(update_fields=["status"])
    return redirect("risks:actions")

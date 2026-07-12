from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render

from engagements.models import Engagement

from .models import AgentProposal, AgentRun, AgentSettings
from .services import apply_proposal, reject_proposal, run_patrol

HISTORY_PAGE_SIZE = 20


def _current_engagement(request):
    engagement_id = request.session.get("current_engagement_id")
    if not engagement_id:
        return None
    return get_object_or_404(Engagement, pk=engagement_id)


@login_required
def queue(request):
    engagement = _current_engagement(request)
    if engagement is None:
        return redirect("engagements:select")

    proposals = AgentProposal.objects.filter(
        engagement=engagement, status=AgentProposal.Status.PENDING
    ).select_related("run")
    latest_run = AgentRun.objects.filter(engagement=engagement).first()

    context = {
        "engagement": engagement,
        "nav_active": "autopilot",
        "proposals": proposals,
        "latest_run": latest_run,
    }
    return render(request, "autopilot/queue.html", context)


@login_required
def approve(request, pk):
    engagement = _current_engagement(request)
    if engagement is None:
        return redirect("engagements:select")

    proposal = get_object_or_404(AgentProposal, pk=pk, engagement=engagement)
    if request.method == "POST":
        note = request.POST.get("note", "").strip()
        try:
            apply_proposal(proposal, request.user, note=note)
            messages.success(request, f"「{proposal.title}」を承認し、登録しました。")
        except ValueError as exc:
            messages.error(request, str(exc))
    return redirect("autopilot:queue")


@login_required
def reject(request, pk):
    engagement = _current_engagement(request)
    if engagement is None:
        return redirect("engagements:select")

    proposal = get_object_or_404(AgentProposal, pk=pk, engagement=engagement)
    if request.method == "POST":
        note = request.POST.get("note", "").strip()
        try:
            reject_proposal(proposal, request.user, note=note)
            messages.success(request, f"「{proposal.title}」を却下しました。")
        except ValueError as exc:
            messages.error(request, str(exc))
    return redirect("autopilot:queue")


@login_required
def history(request):
    engagement = _current_engagement(request)
    if engagement is None:
        return redirect("engagements:select")

    tab = request.GET.get("tab", "proposals")
    if tab == "runs":
        items = AgentRun.objects.filter(engagement=engagement)
    else:
        items = AgentProposal.objects.filter(engagement=engagement).exclude(
            status=AgentProposal.Status.PENDING
        )

    paginator = Paginator(items, HISTORY_PAGE_SIZE)
    page_obj = paginator.get_page(request.GET.get("page"))

    context = {
        "engagement": engagement,
        "nav_active": "autopilot",
        "tab": tab,
        "page_obj": page_obj,
    }
    return render(request, "autopilot/history.html", context)


@login_required
def settings_view(request):
    engagement = _current_engagement(request)
    if engagement is None:
        return redirect("engagements:select")

    agent_settings, _created = AgentSettings.objects.get_or_create(engagement=engagement)

    if request.method == "POST":
        agent_settings.enabled = request.POST.get("enabled") == "on"
        agent_settings.stagnant_spike_threshold = int(
            request.POST.get("stagnant_spike_threshold") or 5
        )
        agent_settings.defect_spike_threshold = int(
            request.POST.get("defect_spike_threshold") or 5
        )
        agent_settings.overdue_threshold = int(request.POST.get("overdue_threshold") or 3)
        agent_settings.max_llm_calls_per_day = int(
            request.POST.get("max_llm_calls_per_day") or 20
        )
        agent_settings.save()
        messages.success(request, "自律運転設定を更新しました。")
        return redirect("autopilot:settings")

    context = {
        "engagement": engagement,
        "nav_active": "autopilot",
        "agent_settings": agent_settings,
    }
    return render(request, "autopilot/settings.html", context)


@login_required
def run_now(request):
    engagement = _current_engagement(request)
    if engagement is None:
        return redirect("engagements:select")

    if request.method == "POST":
        run = run_patrol(engagement, trigger=AgentRun.Trigger.MANUAL, user=request.user)
        if run.status == AgentRun.Status.SUCCESS:
            messages.success(
                request,
                f"巡回が完了しました。検知{run.findings_count}件・新規提案{run.proposals_count}件。",
            )
        else:
            messages.error(request, f"巡回に失敗しました: {run.error_message}")
    return redirect("autopilot:queue")

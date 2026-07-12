from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render

from engagements.models import Engagement
from llm.providers.base import LlmError

from . import services
from .models import TpiAnswer, TpiAssessment, TpiCheckpoint, TpiKeyArea


def _current_engagement(request):
    engagement_id = request.session.get("current_engagement_id")
    if not engagement_id:
        return None
    return get_object_or_404(Engagement, pk=engagement_id)


@login_required
def assessment_list(request):
    engagement = _current_engagement(request)
    if engagement is None:
        return redirect("engagements:select")

    if request.method == "POST":
        title = request.POST.get("title", "").strip() or "TPIアセスメント"
        assessment = TpiAssessment.objects.create(
            engagement=engagement, title=title, assessed_by=request.user
        )
        return redirect("tpi:detail", pk=assessment.pk)

    paginator = Paginator(engagement.tpi_assessments.all(), 15)
    context = {
        "engagement": engagement,
        "nav_active": "tpi",
        "page_obj": paginator.get_page(request.GET.get("page")),
    }
    return render(request, "tpi/list.html", context)


@login_required
def assessment_detail(request, pk):
    engagement = _current_engagement(request)
    if engagement is None:
        return redirect("engagements:select")

    assessment = get_object_or_404(TpiAssessment, pk=pk, engagement=engagement)
    context = {
        "engagement": engagement,
        "nav_active": "tpi",
        "assessment": assessment,
        "matrix": services.assessment_matrix(assessment),
    }
    return render(request, "tpi/detail.html", context)


@login_required
def answer_key_area(request, pk, key_area_pk):
    engagement = _current_engagement(request)
    if engagement is None:
        return redirect("engagements:select")

    assessment = get_object_or_404(TpiAssessment, pk=pk, engagement=engagement)
    key_area = get_object_or_404(TpiKeyArea, pk=key_area_pk)
    checkpoints = TpiCheckpoint.objects.filter(key_area=key_area)

    if assessment.status == TpiAssessment.Status.FINAL:
        messages.error(request, "確定済みのアセスメントは編集できません。")
        return redirect("tpi:detail", pk=pk)

    if request.method == "POST":
        for checkpoint in checkpoints:
            result = request.POST.get(f"result_{checkpoint.pk}", TpiAnswer.Result.NOT_MET)
            note = request.POST.get(f"note_{checkpoint.pk}", "")
            TpiAnswer.objects.update_or_create(
                assessment=assessment,
                checkpoint=checkpoint,
                defaults={"result": result, "note": note},
            )
        messages.success(request, f"{key_area.name} の回答を保存しました。")
        return redirect("tpi:detail", pk=pk)

    answers_by_checkpoint = {
        a.checkpoint_id: a
        for a in TpiAnswer.objects.filter(assessment=assessment, checkpoint__key_area=key_area)
    }
    rows = [
        {
            "checkpoint": checkpoint,
            "result": answers_by_checkpoint[checkpoint.pk].result
            if checkpoint.pk in answers_by_checkpoint
            else TpiAnswer.Result.NOT_MET,
            "note": answers_by_checkpoint[checkpoint.pk].note
            if checkpoint.pk in answers_by_checkpoint
            else "",
        }
        for checkpoint in checkpoints
    ]
    context = {
        "engagement": engagement,
        "nav_active": "tpi",
        "assessment": assessment,
        "key_area": key_area,
        "rows": rows,
    }
    return render(request, "tpi/answer.html", context)


@login_required
def finalize(request, pk):
    engagement = _current_engagement(request)
    if engagement is None:
        return redirect("engagements:select")

    assessment = get_object_or_404(TpiAssessment, pk=pk, engagement=engagement)
    if request.method == "POST":
        assessment.status = TpiAssessment.Status.FINAL
        assessment.save(update_fields=["status"])
        messages.success(request, "アセスメントを確定しました。")
    return redirect("tpi:detail", pk=pk)


@login_required
def suggest(request, pk):
    engagement = _current_engagement(request)
    if engagement is None:
        return redirect("engagements:select")

    assessment = get_object_or_404(TpiAssessment, pk=pk, engagement=engagement)
    if request.method == "POST":
        try:
            assessment.suggestion = services.generate_suggestion(assessment, user=request.user)
            assessment.save(update_fields=["suggestion"])
            messages.success(request, "改善提言を生成しました。")
        except LlmError as exc:
            messages.error(request, f"改善提言の生成に失敗しました: {exc}")
    return redirect("tpi:detail", pk=pk)

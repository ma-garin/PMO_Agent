from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from audit.services import record
from config.csv_utils import csv_response
from config.http_utils import parse_int, parse_optional_number
from engagements.models import Engagement
from llm.providers.base import LlmError

from . import services
from .models import QualityGate, TestPlan, TestProgressEntry


def _current_engagement(request):
    engagement_id = request.session.get("current_engagement_id")
    if not engagement_id:
        return None
    return get_object_or_404(Engagement, pk=engagement_id)


# --- テスト計画 ---


@login_required
def plan_list(request):
    engagement = _current_engagement(request)
    if engagement is None:
        return redirect("engagements:select")

    context = {
        "engagement": engagement,
        "nav_active": "testmgmt",
        "plans": engagement.test_plans.all(),
    }
    return render(request, "testmgmt/plan_list.html", context)


@login_required
def plan_create(request):
    engagement = _current_engagement(request)
    if engagement is None:
        return redirect("engagements:select")

    if request.method != "POST":
        return redirect("testmgmt:plans")

    kind = request.POST.get("kind", TestPlan.Kind.MASTER)
    test_level = request.POST.get("test_level", "").strip()
    title = request.POST.get("title", "").strip() or "テスト計画"
    use_ai = request.POST.get("use_ai") == "1"

    plan = TestPlan.objects.create(
        engagement=engagement, kind=kind, test_level=test_level, title=title, created_by=request.user
    )
    if use_ai:
        try:
            plan.body = services.generate_plan_draft(engagement, kind, test_level, user=request.user)
            plan.save(update_fields=["body"])
        except LlmError as exc:
            messages.error(request, f"AIドラフト生成に失敗しました: {exc}")

    return redirect("testmgmt:plan_edit", pk=plan.pk)


@login_required
def plan_edit(request, pk):
    engagement = _current_engagement(request)
    if engagement is None:
        return redirect("engagements:select")

    plan = get_object_or_404(TestPlan, pk=pk, engagement=engagement)

    if request.method == "POST":
        if plan.status == TestPlan.Status.APPROVED:
            messages.error(request, "承認済みの計画は編集できません。")
            return redirect("testmgmt:plan_edit", pk=pk)

        action = request.POST.get("action")
        if action == "approve":
            plan.status = TestPlan.Status.APPROVED
            plan.approved_by = request.user
            plan.approved_at = timezone.now()
            plan.save(update_fields=["status", "approved_by", "approved_at"])
            record(request.user, "test_plan_approve", plan, detail=plan.title)
            messages.success(request, "計画を承認しました。")
        else:
            plan.body = request.POST.get("body", "")
            plan.save(update_fields=["body"])
            messages.success(request, "保存しました。")
        return redirect("testmgmt:plan_edit", pk=pk)

    return render(
        request, "testmgmt/plan_edit.html", {"engagement": engagement, "nav_active": "testmgmt", "plan": plan}
    )


# --- テスト進捗 ---


@login_required
def progress_export_csv(request):
    engagement = _current_engagement(request)
    if engagement is None:
        return redirect("engagements:select")

    entries = TestProgressEntry.objects.filter(engagement=engagement).order_by("test_level", "date")
    header = ["テストレベル", "日付", "計画累計", "実行累計", "合格累計", "メモ"]
    rows = (
        [e.test_level, e.date, e.planned_cases, e.executed_cases, e.passed_cases, e.note]
        for e in entries
    )
    return csv_response("test_progress.csv", header, rows)


@login_required
def progress_view(request):
    engagement = _current_engagement(request)
    if engagement is None:
        return redirect("engagements:select")

    summary_rows = services.progress_summary(engagement)
    selected_level = request.GET.get("level") or (summary_rows[0]["test_level"] if summary_rows else "")
    series = services.progress_series(engagement, selected_level) if selected_level else []

    context = {
        "engagement": engagement,
        "nav_active": "testmgmt",
        "summary_rows": summary_rows,
        "series": series,
        "selected_level": selected_level,
        "today": timezone.localdate(),
    }
    return render(request, "testmgmt/progress.html", context)


@login_required
def progress_entry_create(request):
    engagement = _current_engagement(request)
    if engagement is None:
        return redirect("engagements:select")

    if request.method == "POST":
        TestProgressEntry.objects.update_or_create(
            engagement=engagement,
            test_level=request.POST.get("test_level", "").strip(),
            date=request.POST.get("date"),
            defaults={
                "planned_cases": parse_int(request.POST.get("planned_cases"), 0, minimum=0),
                "executed_cases": parse_int(request.POST.get("executed_cases"), 0, minimum=0),
                "passed_cases": parse_int(request.POST.get("passed_cases"), 0, minimum=0),
                "note": request.POST.get("note", ""),
            },
        )
        messages.success(request, "実績を記録しました。")
    return redirect("testmgmt:progress")


@login_required
def progress_csv_import(request):
    engagement = _current_engagement(request)
    if engagement is None:
        return redirect("engagements:select")

    if request.method == "POST" and request.FILES.get("file"):
        imported, errors = services.import_progress_csv(engagement, request.FILES["file"])
        messages.success(request, f"{imported}件を取込みました。")
        for err in errors[:10]:
            messages.error(request, err)
    return redirect("testmgmt:progress")


# --- 品質ゲート ---


@login_required
def gate_list(request):
    engagement = _current_engagement(request)
    if engagement is None:
        return redirect("engagements:select")

    return render(
        request,
        "testmgmt/gate_list.html",
        {"engagement": engagement, "nav_active": "testmgmt", "gates": engagement.quality_gates.all()},
    )


@login_required
def gate_create(request):
    engagement = _current_engagement(request)
    if engagement is None:
        return redirect("engagements:select")

    if request.method == "POST":
        criteria = {}
        for key in ("min_execution_rate", "min_pass_rate", "max_open_defects", "max_high_risks"):
            parsed = parse_optional_number(request.POST.get(key), as_float="rate" in key)
            if parsed is not None:
                criteria[key] = parsed
        QualityGate.objects.create(
            engagement=engagement, name=request.POST.get("name", "品質ゲート"), criteria=criteria
        )
        messages.success(request, "品質ゲートを作成しました。")
        return redirect("testmgmt:gates")

    return render(request, "testmgmt/gate_form.html", {"engagement": engagement, "nav_active": "testmgmt"})


@login_required
def gate_detail(request, pk):
    engagement = _current_engagement(request)
    if engagement is None:
        return redirect("engagements:select")

    gate = get_object_or_404(QualityGate, pk=pk, engagement=engagement)
    evaluation = services.evaluate_gate(gate)

    if request.method == "POST":
        verdict = request.POST.get("verdict")
        if verdict in QualityGate.Verdict.values:
            gate.verdict = verdict
            gate.judged_by = request.user
            gate.judged_at = timezone.now()
            gate.note = request.POST.get("note", "")
            gate.save(update_fields=["verdict", "judged_by", "judged_at", "note"])
            record(
                request.user, "quality_gate_judge", gate, detail=f"{gate.name}: {verdict}"
            )
            messages.success(request, "判定を記録しました。")
        return redirect("testmgmt:gate_detail", pk=pk)

    context = {
        "engagement": engagement,
        "nav_active": "testmgmt",
        "gate": gate,
        "evaluation": evaluation,
    }
    return render(request, "testmgmt/gate_detail.html", context)

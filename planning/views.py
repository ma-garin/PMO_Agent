from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_date

from config.http_utils import parse_int
from engagements.models import Engagement

from .models import Schedule, WorkItem
from .services import DEFAULT_ZOOM, ZOOM_PIXELS_PER_DAY, gantt_chart_data


def _current_engagement(request):
    engagement_id = request.session.get("current_engagement_id")
    if not engagement_id:
        return None
    return get_object_or_404(Engagement, pk=engagement_id)


@login_required
def gantt(request):
    engagement = _current_engagement(request)
    if engagement is None:
        return redirect("engagements:select")

    zoom = request.GET.get("zoom", DEFAULT_ZOOM)
    if zoom not in ZOOM_PIXELS_PER_DAY:
        zoom = DEFAULT_ZOOM

    schedule = Schedule.objects.filter(engagement=engagement).first()
    chart = gantt_chart_data(schedule, zoom=zoom) if schedule else None
    items = list(schedule.items.select_related("owner", "improvement_action")) if schedule else []

    context = {
        "engagement": engagement,
        "nav_active": "planning",
        "schedule": schedule,
        "chart": chart,
        "items": items,
        "zoom": zoom,
        "zoom_choices": list(ZOOM_PIXELS_PER_DAY.keys()),
    }
    return render(request, "planning/gantt.html", context)


def _work_item_form_context(engagement, schedule, item=None):
    parents = list(schedule.items.all()) if schedule else []
    if item and item.pk:
        parents = [p for p in parents if p.pk != item.pk]
    return {
        "engagement": engagement,
        "nav_active": "planning",
        "item": item,
        "kind_choices": WorkItem.Kind.choices,
        "status_choices": WorkItem.Status.choices,
        "parents": parents,
        "members": engagement.members.all(),
    }


def _apply_work_item_fields(request, engagement, item):
    item.wbs_code = request.POST.get("wbs_code", "").strip()
    item.title = request.POST.get("title", "").strip()
    kind = request.POST.get("kind", "")
    item.kind = kind if kind in WorkItem.Kind.values else WorkItem.Kind.TASK
    status = request.POST.get("status", "")
    item.status = status if status in WorkItem.Status.values else WorkItem.Status.PLANNED
    item.start_date = parse_date(request.POST.get("start_date", "").strip() or "")
    item.finish_date = parse_date(request.POST.get("finish_date", "").strip() or "")
    item.progress = parse_int(request.POST.get("progress"), 0, minimum=0, maximum=100)
    parent_id = request.POST.get("parent") or ""
    item.parent = item.schedule.items.filter(pk=parent_id).first() if parent_id else None
    owner_id = request.POST.get("owner") or ""
    item.owner = engagement.members.filter(pk=owner_id).first() if owner_id else None
    return item


def _save_work_item(request, engagement, schedule, item, success_message):
    if not (item.wbs_code and item.title and item.start_date and item.finish_date):
        messages.error(request, "WBS・作業名・開始日・終了日は必須です。")
        return None
    try:
        item.save()
    except ValidationError as exc:
        messages.error(request, "入力エラー: " + " / ".join(exc.messages))
        return None
    messages.success(request, success_message)
    return item


@login_required
def work_item_create(request):
    engagement = _current_engagement(request)
    if engagement is None:
        return redirect("engagements:select")

    schedule = Schedule.objects.filter(engagement=engagement).first()
    if request.method == "POST":
        if schedule is None:
            schedule = Schedule.objects.create(
                engagement=engagement, status_date=timezone.localdate()
            )
        item = _apply_work_item_fields(request, engagement, WorkItem(schedule=schedule))
        if _save_work_item(request, engagement, schedule, item, "タスクを追加しました。"):
            return redirect("planning:gantt")
        return render(request, "planning/work_item_form.html",
                      _work_item_form_context(engagement, schedule, item))

    return render(request, "planning/work_item_form.html",
                  _work_item_form_context(engagement, schedule))


@login_required
def work_item_edit(request, pk):
    engagement = _current_engagement(request)
    if engagement is None:
        return redirect("engagements:select")

    item = get_object_or_404(WorkItem, pk=pk, schedule__engagement=engagement)
    schedule = item.schedule
    if request.method == "POST":
        _apply_work_item_fields(request, engagement, item)
        if _save_work_item(request, engagement, schedule, item, "タスクを更新しました。"):
            return redirect("planning:gantt")

    return render(request, "planning/work_item_form.html",
                  _work_item_form_context(engagement, schedule, item))


@login_required
def work_item_delete(request, pk):
    engagement = _current_engagement(request)
    if engagement is None:
        return redirect("engagements:select")

    item = get_object_or_404(WorkItem, pk=pk, schedule__engagement=engagement)
    if request.method == "POST":
        item.delete()
        messages.success(request, "タスクを削除しました。")
    return redirect("planning:gantt")

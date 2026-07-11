from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from functools import reduce
from operator import or_

from django.db.models import Q, QuerySet
from django.utils import timezone

from engagements.models import Engagement
from llm.services import LlmError, run_completion
from tickets.adapters.base import is_done_status_name
from tickets.models import Notification, Ticket

from .models import OdcClassification, WeeklyDigest

DEFAULT_DEFECT_TYPES = ["bug", "バグ", "障害", "不具合", "defect"]


def defect_type_values(engagement: Engagement) -> list[str]:
    return engagement.defect_ticket_types or DEFAULT_DEFECT_TYPES


def get_defects(engagement: Engagement) -> QuerySet[Ticket]:
    values = defect_type_values(engagement)
    condition = reduce(or_, (Q(ticket_type__iexact=v) for v in values))
    return Ticket.objects.filter(source__engagement=engagement).filter(condition)


def summarize_defects(engagement: Engagement) -> dict:
    defects = get_defects(engagement)
    today = timezone.localdate()
    total = defects.count()
    closed = defects.filter(is_done=True).count()
    open_count = total - closed
    overdue = defects.filter(is_done=False, due_date__lt=today).count()

    density = None
    if engagement.size_metric_value and total:
        density = round(Decimal(total) / engagement.size_metric_value, 3)

    # 滞留: 未クローズ欠陥の経過日数平均(作成日時が取れているもののみ)
    now = timezone.now()
    open_ages = [
        (now - t.source_created_at).days
        for t in defects.filter(is_done=False, source_created_at__isnull=False)
    ]
    avg_open_age = round(sum(open_ages) / len(open_ages), 1) if open_ages else None

    return {
        "total": total,
        "open": open_count,
        "closed": closed,
        "overdue": overdue,
        "density": density,
        "avg_open_age_days": avg_open_age,
    }


def convergence_series(engagement: Engagement) -> list[dict]:
    """週次の累積オープン/クローズ件数(収束曲線の元データ)。"""
    defects = list(
        get_defects(engagement).filter(source_created_at__isnull=False)
    )
    if not defects:
        return []

    start = min(t.source_created_at for t in defects).date()
    end = timezone.localdate()
    # 週の境界を月曜に揃える
    start -= timedelta(days=start.weekday())

    series: list[dict] = []
    week_start = start
    while week_start <= end:
        week_end = week_start + timedelta(days=6)
        boundary = min(week_end, end)
        opened = sum(1 for t in defects if t.source_created_at.date() <= boundary)
        closed = sum(
            1
            for t in defects
            if t.closed_at is not None and t.closed_at.date() <= boundary
        )
        series.append(
            {
                "label": f"{week_start.month}/{week_start.day}",
                "opened": opened,
                "closed": closed,
            }
        )
        week_start += timedelta(days=7)
    return series


def convergence_svg_points(series: list[dict], width: int = 600, height: int = 160) -> dict:
    """収束曲線をSVG polyline用の座標文字列に変換する。"""
    if not series:
        return {"opened": "", "closed": "", "max": 0}
    max_value = max(point["opened"] for point in series) or 1
    n = len(series)
    step = width / max(n - 1, 1)

    def points_for(key: str) -> str:
        coords = []
        for i, point in enumerate(series):
            x = round(i * step, 1)
            y = round(height - (point[key] / max_value) * height, 1)
            coords.append(f"{x},{y}")
        return " ".join(coords)

    return {"opened": points_for("opened"), "closed": points_for("closed"), "max": max_value}


def odc_distribution(engagement: Engagement) -> dict:
    """確定済みODC分類の軸別分布と未分類件数。"""
    defects = get_defects(engagement)
    total = defects.count()
    confirmed = OdcClassification.objects.filter(
        ticket__in=defects, status=OdcClassification.Status.CONFIRMED
    )

    def axis_counts(field: str, choices) -> list[dict]:
        counts: list[dict] = []
        confirmed_max = confirmed.count() or 1
        for value, label in choices.choices:
            count = confirmed.filter(**{field: value}).count()
            if count:
                counts.append(
                    {
                        "label": label,
                        "count": count,
                        "percent": round(count / confirmed_max * 100),
                    }
                )
        return sorted(counts, key=lambda item: -item["count"])

    return {
        "confirmed_count": confirmed.count(),
        "unclassified_count": total - confirmed.count(),
        "defect_type": axis_counts("defect_type", OdcClassification.DefectType),
        "trigger": axis_counts("trigger", OdcClassification.Trigger),
        "activity": axis_counts("activity", OdcClassification.Activity),
        "impact": axis_counts("impact", OdcClassification.Impact),
    }


def reopen_stats(engagement: Engagement) -> dict:
    """ステータス遷移履歴から、クローズ経験のあるチケットのうち再オープンされた割合を算出する。"""
    tickets = Ticket.objects.filter(source__engagement=engagement).prefetch_related(
        "status_transitions"
    )

    closed_count = 0
    reopened_count = 0
    for ticket in tickets:
        was_done = False
        ever_closed = False
        ever_reopened = False
        for transition in ticket.status_transitions.all():
            now_done = is_done_status_name(transition.to_status)
            if now_done:
                ever_closed = True
                was_done = True
            else:
                if was_done:
                    ever_reopened = True
                was_done = False
        if ever_closed:
            closed_count += 1
        if ever_reopened:
            reopened_count += 1

    reopen_rate = round(reopened_count / closed_count * 100, 1) if closed_count else 0.0
    return {
        "reopened_count": reopened_count,
        "closed_count": closed_count,
        "reopen_rate": reopen_rate,
    }


DIGEST_SYSTEM = (
    "あなたはPMO(プロジェクトマネジメントオフィス)のアシスタントです。"
    "案件の週次サマリーを3〜5行の日本語で簡潔に作成してください。"
)


def _week_boundaries(week_start: date) -> tuple[date, date]:
    return week_start, week_start + timedelta(days=6)


def weekly_digest_metrics(engagement: Engagement, week_start: date) -> dict:
    week_start, week_end = _week_boundaries(week_start)
    tickets = Ticket.objects.filter(source__engagement=engagement)
    defects = get_defects(engagement)

    new_defects = defects.filter(
        source_created_at__date__gte=week_start, source_created_at__date__lte=week_end
    ).count()
    closed_defects = defects.filter(
        closed_at__date__gte=week_start, closed_at__date__lte=week_end
    ).count()
    new_notifications = Notification.objects.filter(
        engagement=engagement, created_at__date__gte=week_start, created_at__date__lte=week_end
    ).count()

    total = tickets.count()
    done_as_of_end = tickets.filter(is_done=True, closed_at__date__lte=week_end).count()
    done_as_of_start = tickets.filter(is_done=True, closed_at__date__lt=week_start).count()
    progress_percent = round(done_as_of_end / total * 100) if total else 0
    progress_percent_before = round(done_as_of_start / total * 100) if total else 0

    return {
        "week_start": week_start.isoformat(),
        "week_end": week_end.isoformat(),
        "new_defects": new_defects,
        "closed_defects": closed_defects,
        "new_notifications": new_notifications,
        "progress_percent": progress_percent,
        "progress_change": progress_percent - progress_percent_before,
    }


def _digest_fallback_body(metrics: dict) -> str:
    change = metrics["progress_change"]
    change_text = f"+{change}" if change >= 0 else str(change)
    return (
        f"今週は新規欠陥{metrics['new_defects']}件、クローズ{metrics['closed_defects']}件、"
        f"新規通知{metrics['new_notifications']}件でした。"
        f"進捗率は{metrics['progress_percent']}%（前週比{change_text}pt）です。"
    )


def generate_weekly_digest(
    engagement: Engagement, week_start: date | None = None, user=None
) -> WeeklyDigest:
    if week_start is None:
        today = timezone.localdate()
        this_week_start = today - timedelta(days=today.weekday())
        week_start = this_week_start - timedelta(days=7)

    metrics = weekly_digest_metrics(engagement, week_start)

    prompt = (
        f"以下は案件「{engagement.name}」の今週の指標です。3〜5行の日本語サマリーを書いてください。\n\n"
        f"新規欠陥: {metrics['new_defects']}件\n"
        f"クローズ欠陥: {metrics['closed_defects']}件\n"
        f"新規通知: {metrics['new_notifications']}件\n"
        f"進捗率: {metrics['progress_percent']}%（前週比{metrics['progress_change']:+d}pt）\n"
    )
    try:
        body = run_completion(
            engagement, "weekly_digest", prompt, system=DIGEST_SYSTEM, user=user
        )
    except LlmError:
        body = _digest_fallback_body(metrics)

    digest, _ = WeeklyDigest.objects.update_or_create(
        engagement=engagement,
        week_start=week_start,
        defaults={"body": body, "metrics": metrics},
    )
    return digest

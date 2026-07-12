"""ルールベースの異常検知(確定的判定、LLM不使用)。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from django.utils import timezone

from analytics.services import convergence_series, get_defects, summarize_defects
from tickets.models import Notification

from .models import AgentProposal, AgentSettings


@dataclass(frozen=True)
class Finding:
    rule: str
    title: str
    evidence: dict
    suggested_kind: str


def _stagnant_spike(engagement, settings: AgentSettings) -> Finding | None:
    since = timezone.now() - timedelta(hours=24)
    count = Notification.objects.filter(
        engagement=engagement, kind=Notification.Kind.STAGNANT, created_at__gte=since
    ).count()
    if count < settings.stagnant_spike_threshold:
        return None
    return Finding(
        rule="stagnant_spike",
        title=f"直近24時間で停滞通知が{count}件急増しています",
        evidence={"observed": count, "threshold": settings.stagnant_spike_threshold, "window": "24h"},
        suggested_kind=AgentProposal.Kind.CREATE_ACTION,
    )


def _defect_spike(engagement, settings: AgentSettings) -> Finding | None:
    since = timezone.now() - timedelta(hours=24)
    count = get_defects(engagement).filter(source_created_at__gte=since).count()
    if count < settings.defect_spike_threshold:
        return None
    return Finding(
        rule="defect_spike",
        title=f"直近24時間で新規欠陥が{count}件検出されています",
        evidence={"observed": count, "threshold": settings.defect_spike_threshold, "window": "24h"},
        suggested_kind=AgentProposal.Kind.REGISTER_RISK,
    )


def _overdue_accumulation(engagement, settings: AgentSettings) -> Finding | None:
    count = summarize_defects(engagement)["overdue"]
    if count < settings.overdue_threshold:
        return None
    return Finding(
        rule="overdue_accumulation",
        title=f"未クローズかつ期限超過の欠陥が{count}件蓄積しています",
        evidence={"observed": count, "threshold": settings.overdue_threshold},
        suggested_kind=AgentProposal.Kind.CREATE_ACTION,
    )


def _convergence_stall(engagement, settings: AgentSettings) -> Finding | None:
    series = convergence_series(engagement)
    if len(series) < 2:
        return None
    open_count = summarize_defects(engagement)["open"]
    if open_count <= 0:
        return None
    increment = series[-1]["closed"] - series[-2]["closed"]
    if increment > 0:
        return None
    return Finding(
        rule="convergence_stall",
        title="直近2週間、クローズ件数が増加していません",
        evidence={"increment": increment, "open_count": open_count, "window": "2週"},
        suggested_kind=AgentProposal.Kind.DRAFT_REPORT,
    )


_RULES = (_stagnant_spike, _defect_spike, _overdue_accumulation, _convergence_stall)


def evaluate_rules(engagement, settings: AgentSettings) -> list[Finding]:
    findings = []
    for rule_fn in _RULES:
        finding = rule_fn(engagement, settings)
        if finding is not None:
            findings.append(finding)
    return findings

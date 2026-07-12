"""巡回の実行(run_patrol)と提案の承認/却下(apply_proposal/reject_proposal)。"""

from __future__ import annotations

import json
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from analytics.services import odc_distribution, summarize_defects
from llm.prompt_utils import EXTERNAL_DATA_GUARD
from llm.providers.base import LlmError
from llm.services import run_completion

from .models import AgentProposal, AgentRun, AgentSettings
from .rules import Finding, evaluate_rules

AUTOPILOT_SYSTEM = (
    "あなたは検証会社のPMOエージェントです。検知された異常について、"
    "与えられたデータのみを根拠に①何が起きているか②考えられる原因③推奨アクションを"
    "日本語で簡潔に分析し、指定のJSON形式で出力してください。数値の捏造は禁止します。"
    + EXTERNAL_DATA_GUARD
)

_PAYLOAD_SCHEMA_HINTS = {
    AgentProposal.Kind.REGISTER_RISK: (
        '{"title": "...", "description": "...", "probability": 1-5, '
        '"impact": 1-5, "measurement": "...", "countermeasure": "..."}'
    ),
    AgentProposal.Kind.CREATE_ACTION: '{"title": "...", "background": "...", "due_days": 整数}',
    AgentProposal.Kind.DRAFT_REPORT: '{"title": "...", "period_days": 整数}',
    AgentProposal.Kind.SUMMARY_ONLY: "{}",
}


def _extract_json_object(text: str) -> dict:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        return {}
    try:
        parsed = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _llm_calls_today(engagement) -> int:
    from llm.models import LlmCallLog

    today = timezone.localdate()
    return LlmCallLog.objects.filter(
        engagement=engagement, purpose="autopilot", created_at__date=today
    ).count()


def _format_evidence(evidence: dict) -> str:
    """検知根拠の辞書を日本語ラベル付きの読みやすい文字列に整形する。"""
    if not evidence:
        return "（なし）"
    labels = AgentProposal.EVIDENCE_LABELS
    return " / ".join(f"{labels.get(key, key)}: {value}" for key, value in evidence.items())


def _fallback_body(finding: Finding) -> str:
    return (
        f"【{finding.title}】\n"
        f"検知根拠: {_format_evidence(finding.evidence)}\n"
        "詳細分析にはLLMを利用できなかったため、ルール検知結果のみを表示しています。"
        "内容を確認のうえ判断してください。"
    )


def _fallback_payload(finding: Finding, engagement) -> dict:
    if finding.suggested_kind == AgentProposal.Kind.REGISTER_RISK:
        return {
            "title": finding.title,
            "description": f"ルール({finding.rule})による自動検知。詳細はevidenceを参照してください。",
            "probability": 3,
            "impact": 3,
            "measurement": "",
            "countermeasure": "",
        }
    if finding.suggested_kind == AgentProposal.Kind.CREATE_ACTION:
        return {
            "title": finding.title,
            "background": f"ルール({finding.rule})による自動検知。",
            "due_days": 7,
        }
    if finding.suggested_kind == AgentProposal.Kind.DRAFT_REPORT:
        return {"title": f"{engagement.name} 状況報告", "period_days": 14}
    return {}


def _high_risk_titles(engagement) -> list[str]:
    try:
        from risks.models import RiskItem
    except ImportError:
        return []
    return list(
        RiskItem.objects.filter(engagement=engagement)
        .exclude(status=RiskItem.Status.CLOSED)
        .order_by("-probability", "-impact")
        .values_list("title", flat=True)[:5]
    )


def _build_body_and_payload(
    engagement, finding: Finding, use_llm: bool, user=None
) -> tuple[str, dict]:
    if not use_llm:
        return _fallback_body(finding), _fallback_payload(finding, engagement)

    summary = summarize_defects(engagement)
    odc = odc_distribution(engagement)
    high_risks = _high_risk_titles(engagement)
    schema_hint = _PAYLOAD_SCHEMA_HINTS.get(finding.suggested_kind, "{}")

    prompt = (
        f"検知内容: {finding.title}\n"
        f"検知根拠: {finding.evidence}\n\n"
        f"欠陥サマリー: {summary}\n"
        f"ODC分布(確定済み): {odc}\n"
        f"高リスク一覧: {high_risks}\n\n"
        f'出力は {{"body": "分析文", "payload": {schema_hint}}} の形式のJSONのみとし、'
        "上記データのみを根拠にしてください。"
    )
    try:
        raw = run_completion(engagement, "autopilot", prompt, system=AUTOPILOT_SYSTEM, user=user)
    except LlmError:
        return _fallback_body(finding), _fallback_payload(finding, engagement)

    parsed = _extract_json_object(raw)
    body = str(parsed.get("body") or "").strip() or _fallback_body(finding)
    payload = parsed.get("payload")
    if not isinstance(payload, dict):
        payload = _fallback_payload(finding, engagement)
    return body, payload


def run_patrol(engagement, trigger: str, user=None) -> AgentRun:
    run = AgentRun.objects.create(engagement=engagement, trigger=trigger)
    try:
        agent_settings = getattr(engagement, "agent_settings", None)
        if agent_settings is None:
            agent_settings = AgentSettings(engagement=engagement)

        findings = evaluate_rules(engagement, agent_settings)
        use_llm = _llm_calls_today(engagement) < agent_settings.max_llm_calls_per_day
        today_key = timezone.localdate().isoformat()

        proposals_created = 0
        for finding in findings:
            dedup_key = f"{finding.rule}:{today_key}"
            already_pending = AgentProposal.objects.filter(
                engagement=engagement,
                kind=finding.suggested_kind,
                dedup_key=dedup_key,
                status=AgentProposal.Status.PENDING,
            ).exists()
            if already_pending:
                continue

            body, payload = _build_body_and_payload(engagement, finding, use_llm, user=user)
            AgentProposal.objects.create(
                engagement=engagement,
                run=run,
                kind=finding.suggested_kind,
                dedup_key=dedup_key,
                title=finding.title,
                evidence=finding.evidence,
                body=body,
                payload=payload,
            )
            proposals_created += 1

            try:
                from risks.models import GeneralNotification

                GeneralNotification.objects.get_or_create(
                    engagement=engagement,
                    kind=GeneralNotification.Kind.AGENT_PROPOSAL,
                    message=f"エージェントから提案: {finding.title}",
                )
            except ImportError:
                pass

        run.status = AgentRun.Status.SUCCESS
        run.findings_count = len(findings)
        run.proposals_count = proposals_created
        run.finished_at = timezone.now()
        run.save(update_fields=["status", "findings_count", "proposals_count", "finished_at"])
    except Exception as exc:  # noqa: BLE001 - 巡回自体は失敗させず記録して終える
        run.status = AgentRun.Status.FAILED
        run.error_message = str(exc)
        run.finished_at = timezone.now()
        run.save(update_fields=["status", "error_message", "finished_at"])
    return run


def _clamp_1_5(value) -> int:
    try:
        value = int(value)
    except (TypeError, ValueError):
        return 3
    return max(1, min(5, value))


def _apply_register_risk(proposal: AgentProposal) -> None:
    from risks.models import RiskItem

    payload = proposal.payload or {}
    RiskItem.objects.create(
        engagement=proposal.engagement,
        title=payload.get("title") or proposal.title,
        description=payload.get("description", ""),
        probability=_clamp_1_5(payload.get("probability", 3)),
        impact=_clamp_1_5(payload.get("impact", 3)),
        measurement=payload.get("measurement", ""),
        countermeasure=payload.get("countermeasure", ""),
    )


def _apply_create_action(proposal: AgentProposal) -> None:
    from risks.models import ImprovementAction

    payload = proposal.payload or {}
    try:
        due_days = int(payload.get("due_days"))
    except (TypeError, ValueError):
        due_days = 7
    ImprovementAction.objects.create(
        engagement=proposal.engagement,
        title=payload.get("title") or proposal.title,
        background=payload.get("background", ""),
        origin_note="自律運転エージェントからの提案",
        due_date=timezone.localdate() + timedelta(days=due_days),
    )


def _apply_draft_report(proposal: AgentProposal, user) -> None:
    from reports.models import Report
    from reports.services import generate_draft

    payload = proposal.payload or {}
    try:
        period_days = int(payload.get("period_days"))
    except (TypeError, ValueError):
        period_days = 14

    period_end = timezone.localdate()
    period_start = period_end - timedelta(days=period_days)
    report = Report.objects.create(
        engagement=proposal.engagement,
        title=payload.get("title") or proposal.title,
        period_start=period_start,
        period_end=period_end,
        created_by=user,
    )
    try:
        report.body = generate_draft(proposal.engagement, period_start, period_end, user=user)
        report.save(update_fields=["body"])
    except LlmError:
        pass


_APPLIERS = {
    AgentProposal.Kind.REGISTER_RISK: lambda proposal, user: _apply_register_risk(proposal),
    AgentProposal.Kind.CREATE_ACTION: lambda proposal, user: _apply_create_action(proposal),
    AgentProposal.Kind.DRAFT_REPORT: _apply_draft_report,
    AgentProposal.Kind.SUMMARY_ONLY: lambda proposal, user: None,
}


def _lock_pending_proposal(proposal: AgentProposal) -> AgentProposal:
    locked_proposal = AgentProposal.objects.select_for_update().get(pk=proposal.pk)
    if locked_proposal.status != AgentProposal.Status.PENDING:
        raise ValueError("既に判断済みの提案です。")
    return locked_proposal


@transaction.atomic
def apply_proposal(proposal: AgentProposal, user, note: str = "") -> None:
    locked_proposal = _lock_pending_proposal(proposal)

    applier = _APPLIERS.get(locked_proposal.kind)
    if applier is not None:
        applier(locked_proposal, user)

    locked_proposal.status = AgentProposal.Status.APPROVED
    locked_proposal.decided_by = user
    locked_proposal.decided_at = timezone.now()
    locked_proposal.decision_note = note
    locked_proposal.save(update_fields=["status", "decided_by", "decided_at", "decision_note"])

    try:
        from audit.services import record

        record(
            user,
            "agent_proposal_approve",
            locked_proposal,
            detail=locked_proposal.title,
        )
    except ImportError:
        pass


@transaction.atomic
def reject_proposal(proposal: AgentProposal, user, note: str = "") -> None:
    locked_proposal = _lock_pending_proposal(proposal)

    locked_proposal.status = AgentProposal.Status.REJECTED
    locked_proposal.decided_by = user
    locked_proposal.decided_at = timezone.now()
    locked_proposal.decision_note = note
    locked_proposal.save(update_fields=["status", "decided_by", "decided_at", "decision_note"])

    try:
        from audit.services import record

        record(user, "agent_proposal_reject", locked_proposal, detail=note)
    except ImportError:
        pass

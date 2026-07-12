from datetime import timedelta
from unittest.mock import patch

import pytest
from django.utils import timezone

from autopilot.models import AgentProposal, AgentRun, AgentSettings
from autopilot.services import apply_proposal, reject_proposal, run_patrol
from llm.providers.base import LlmError
from llm.models import LlmCallLog
from reports.models import Report
from risks.models import GeneralNotification, ImprovementAction, RiskItem
from tickets.models import Ticket


def _make_stagnant_finding_data(engagement, source):
    """stagnant_spikeが発火するデータを作る(CREATE_ACTION提案)。"""
    from tickets.models import Notification

    for i in range(6):
        ticket = Ticket.objects.create(source=source, external_id=str(i), summary=f"t{i}")
        Notification.objects.create(
            engagement=engagement, ticket=ticket, kind=Notification.Kind.STAGNANT, message="停滞"
        )


@pytest.mark.django_db
class TestRunPatrol:
    def test_finding_creates_pending_proposal(self, engagement, source):
        _make_stagnant_finding_data(engagement, source)
        with patch("autopilot.services.run_completion", return_value='{"body": "分析", "payload": {}}'):
            run = run_patrol(engagement, trigger="manual")

        assert run.status == AgentRun.Status.SUCCESS
        assert run.proposals_count == 1
        proposals = AgentProposal.objects.filter(engagement=engagement)
        assert proposals.count() == 1
        assert proposals.first().status == AgentProposal.Status.PENDING

    def test_second_patrol_same_day_does_not_duplicate(self, engagement, source):
        _make_stagnant_finding_data(engagement, source)
        with patch("autopilot.services.run_completion", return_value='{"body": "分析", "payload": {}}'):
            run_patrol(engagement, trigger="manual")
            run_patrol(engagement, trigger="manual")

        assert AgentProposal.objects.filter(engagement=engagement).count() == 1

    def test_llm_call_limit_exceeded_uses_fallback_body(self, engagement, source):
        agent_settings = AgentSettings.objects.create(engagement=engagement, max_llm_calls_per_day=1)
        LlmCallLog.objects.create(
            engagement=engagement, provider="claude", purpose="autopilot",
            prompt_chars=1, response_chars=1, status=LlmCallLog.Status.SUCCESS,
        )
        _make_stagnant_finding_data(engagement, source)

        with patch("autopilot.services.run_completion") as mock_run:
            run_patrol(engagement, trigger="manual")

        mock_run.assert_not_called()
        proposal = AgentProposal.objects.get(engagement=engagement)
        assert "検知根拠" in proposal.body

    def test_llm_error_falls_back_and_run_still_succeeds(self, engagement, source):
        _make_stagnant_finding_data(engagement, source)
        with patch("autopilot.services.run_completion", side_effect=LlmError("down")):
            run = run_patrol(engagement, trigger="manual")

        assert run.status == AgentRun.Status.SUCCESS
        proposal = AgentProposal.objects.get(engagement=engagement)
        assert "検知根拠" in proposal.body

    def test_proposal_creation_triggers_general_notification(self, engagement, source):
        _make_stagnant_finding_data(engagement, source)
        with patch("autopilot.services.run_completion", return_value='{"body": "分析", "payload": {}}'):
            run_patrol(engagement, trigger="manual")

        assert GeneralNotification.objects.filter(
            engagement=engagement, kind=GeneralNotification.Kind.AGENT_PROPOSAL
        ).exists()

    def test_no_findings_means_success_with_zero_proposals(self, engagement):
        run = run_patrol(engagement, trigger="manual")
        assert run.status == AgentRun.Status.SUCCESS
        assert run.findings_count == 0
        assert run.proposals_count == 0

    def test_unexpected_exception_marks_run_failed_without_raising(self, engagement, source):
        _make_stagnant_finding_data(engagement, source)
        with patch("autopilot.services.evaluate_rules", side_effect=RuntimeError("boom")):
            run = run_patrol(engagement, trigger="manual")

        assert run.status == AgentRun.Status.FAILED
        assert "boom" in run.error_message


@pytest.mark.django_db
class TestApplyProposal:
    def _make_proposal(self, engagement, kind, payload):
        run = AgentRun.objects.create(engagement=engagement, trigger="manual")
        return AgentProposal.objects.create(
            engagement=engagement, run=run, kind=kind, dedup_key="k",
            title="提案タイトル", evidence={}, body="分析文", payload=payload,
        )

    def test_register_risk_creates_risk_item(self, engagement, owner):
        proposal = self._make_proposal(
            engagement, AgentProposal.Kind.REGISTER_RISK,
            {"title": "リスクA", "description": "d", "probability": 4, "impact": 5,
             "measurement": "m", "countermeasure": "c"},
        )
        apply_proposal(proposal, owner)

        risk = RiskItem.objects.get(engagement=engagement)
        assert risk.title == "リスクA"
        assert risk.probability == 4
        assert risk.impact == 5
        proposal.refresh_from_db()
        assert proposal.status == AgentProposal.Status.APPROVED
        assert proposal.decided_by == owner

    def test_register_risk_clamps_out_of_range_values(self, engagement, owner):
        proposal = self._make_proposal(
            engagement, AgentProposal.Kind.REGISTER_RISK,
            {"title": "リスクB", "probability": 99, "impact": -5},
        )
        apply_proposal(proposal, owner)
        risk = RiskItem.objects.get(engagement=engagement)
        assert risk.probability == 5
        assert risk.impact == 1

    def test_create_action_sets_due_date_from_due_days(self, engagement, owner):
        proposal = self._make_proposal(
            engagement, AgentProposal.Kind.CREATE_ACTION,
            {"title": "アクションA", "background": "b", "due_days": 10},
        )
        apply_proposal(proposal, owner)

        action = ImprovementAction.objects.get(engagement=engagement)
        assert action.title == "アクションA"
        assert action.due_date == timezone.localdate() + timedelta(days=10)

    def test_create_action_missing_due_days_defaults_to_seven(self, engagement, owner):
        proposal = self._make_proposal(
            engagement, AgentProposal.Kind.CREATE_ACTION, {"title": "アクションB"}
        )
        apply_proposal(proposal, owner)
        action = ImprovementAction.objects.get(engagement=engagement)
        assert action.due_date == timezone.localdate() + timedelta(days=7)

    def test_draft_report_creates_report_with_generated_body(self, engagement, owner):
        proposal = self._make_proposal(
            engagement, AgentProposal.Kind.DRAFT_REPORT,
            {"title": "状況報告", "period_days": 14},
        )
        with patch("reports.services.generate_draft", return_value="# 報告書\n本文"):
            apply_proposal(proposal, owner)

        report = Report.objects.get(engagement=engagement)
        assert report.title == "状況報告"
        assert report.body == "# 報告書\n本文"

    def test_summary_only_creates_nothing(self, engagement, owner):
        proposal = self._make_proposal(engagement, AgentProposal.Kind.SUMMARY_ONLY, {})
        apply_proposal(proposal, owner)

        assert not RiskItem.objects.filter(engagement=engagement).exists()
        assert not ImprovementAction.objects.filter(engagement=engagement).exists()
        assert not Report.objects.filter(engagement=engagement).exists()
        proposal.refresh_from_db()
        assert proposal.status == AgentProposal.Status.APPROVED

    def test_double_approval_raises(self, engagement, owner):
        proposal = self._make_proposal(engagement, AgentProposal.Kind.SUMMARY_ONLY, {})
        apply_proposal(proposal, owner)
        with pytest.raises(ValueError):
            apply_proposal(proposal, owner)

    def test_reject_records_decision_without_registering(self, engagement, owner):
        proposal = self._make_proposal(
            engagement, AgentProposal.Kind.REGISTER_RISK, {"title": "リスクC"}
        )
        reject_proposal(proposal, owner, note="不要")

        proposal.refresh_from_db()
        assert proposal.status == AgentProposal.Status.REJECTED
        assert proposal.decision_note == "不要"
        assert not RiskItem.objects.filter(engagement=engagement).exists()

    def test_double_reject_raises(self, engagement, owner):
        proposal = self._make_proposal(engagement, AgentProposal.Kind.SUMMARY_ONLY, {})
        reject_proposal(proposal, owner)
        with pytest.raises(ValueError):
            reject_proposal(proposal, owner)

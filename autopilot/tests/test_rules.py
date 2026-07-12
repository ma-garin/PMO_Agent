from datetime import timedelta

import pytest
from django.utils import timezone

from autopilot.models import AgentSettings
from autopilot.rules import evaluate_rules
from tickets.models import Notification, Ticket


def _settings(engagement, **overrides) -> AgentSettings:
    defaults = dict(
        stagnant_spike_threshold=5,
        defect_spike_threshold=5,
        overdue_threshold=3,
        max_llm_calls_per_day=20,
    )
    defaults.update(overrides)
    return AgentSettings(engagement=engagement, **defaults)


def _rule_names(findings) -> set[str]:
    return {f.rule for f in findings}


@pytest.mark.django_db
class TestStagnantSpike:
    def test_fires_exactly_at_threshold(self, engagement, source):
        settings_obj = _settings(engagement, stagnant_spike_threshold=3)
        for i in range(3):
            ticket = Ticket.objects.create(source=source, external_id=str(i), summary=f"t{i}")
            Notification.objects.create(
                engagement=engagement, ticket=ticket, kind=Notification.Kind.STAGNANT, message="停滞"
            )
        findings = evaluate_rules(engagement, settings_obj)
        assert "stagnant_spike" in _rule_names(findings)

    def test_does_not_fire_below_threshold(self, engagement, source):
        settings_obj = _settings(engagement, stagnant_spike_threshold=3)
        for i in range(2):
            ticket = Ticket.objects.create(source=source, external_id=str(i), summary=f"t{i}")
            Notification.objects.create(
                engagement=engagement, ticket=ticket, kind=Notification.Kind.STAGNANT, message="停滞"
            )
        findings = evaluate_rules(engagement, settings_obj)
        assert "stagnant_spike" not in _rule_names(findings)

    def test_old_notifications_outside_24h_window_are_excluded(self, engagement, source):
        settings_obj = _settings(engagement, stagnant_spike_threshold=1)
        ticket = Ticket.objects.create(source=source, external_id="1", summary="t")
        notification = Notification.objects.create(
            engagement=engagement, ticket=ticket, kind=Notification.Kind.STAGNANT, message="停滞"
        )
        Notification.objects.filter(pk=notification.pk).update(
            created_at=timezone.now() - timedelta(hours=25)
        )
        findings = evaluate_rules(engagement, settings_obj)
        assert "stagnant_spike" not in _rule_names(findings)


@pytest.mark.django_db
class TestDefectSpike:
    def test_fires_exactly_at_threshold(self, engagement, source):
        settings_obj = _settings(engagement, defect_spike_threshold=2)
        now = timezone.now()
        for i in range(2):
            Ticket.objects.create(
                source=source, external_id=str(i), summary=f"d{i}", ticket_type="Bug",
                source_created_at=now,
            )
        findings = evaluate_rules(engagement, settings_obj)
        assert "defect_spike" in _rule_names(findings)

    def test_does_not_fire_below_threshold(self, engagement, source):
        settings_obj = _settings(engagement, defect_spike_threshold=2)
        Ticket.objects.create(
            source=source, external_id="1", summary="d1", ticket_type="Bug",
            source_created_at=timezone.now(),
        )
        findings = evaluate_rules(engagement, settings_obj)
        assert "defect_spike" not in _rule_names(findings)


@pytest.mark.django_db
class TestOverdueAccumulation:
    def test_fires_exactly_at_threshold(self, engagement, source):
        settings_obj = _settings(engagement, overdue_threshold=2)
        yesterday = timezone.localdate() - timedelta(days=1)
        for i in range(2):
            Ticket.objects.create(
                source=source, external_id=str(i), summary=f"d{i}", ticket_type="Bug",
                is_done=False, due_date=yesterday,
            )
        findings = evaluate_rules(engagement, settings_obj)
        assert "overdue_accumulation" in _rule_names(findings)

    def test_does_not_fire_below_threshold(self, engagement, source):
        settings_obj = _settings(engagement, overdue_threshold=2)
        yesterday = timezone.localdate() - timedelta(days=1)
        Ticket.objects.create(
            source=source, external_id="1", summary="d1", ticket_type="Bug",
            is_done=False, due_date=yesterday,
        )
        findings = evaluate_rules(engagement, settings_obj)
        assert "overdue_accumulation" not in _rule_names(findings)


@pytest.mark.django_db
class TestConvergenceStall:
    def test_fires_when_no_closures_in_last_two_weeks_and_open_exists(self, engagement, source):
        settings_obj = _settings(engagement)
        Ticket.objects.create(
            source=source, external_id="1", summary="d1", ticket_type="Bug",
            is_done=False, source_created_at=timezone.now() - timedelta(days=20),
        )
        findings = evaluate_rules(engagement, settings_obj)
        assert "convergence_stall" in _rule_names(findings)
        finding = next(f for f in findings if f.rule == "convergence_stall")
        assert finding.evidence["increment"] == 0

    def test_does_not_fire_when_recently_closed(self, engagement, source):
        settings_obj = _settings(engagement)
        now = timezone.now()
        Ticket.objects.create(
            source=source, external_id="1", summary="d1", ticket_type="Bug",
            is_done=True, source_created_at=now - timedelta(days=20), closed_at=now,
        )
        Ticket.objects.create(
            source=source, external_id="2", summary="d2", ticket_type="Bug",
            is_done=False, source_created_at=now - timedelta(days=20),
        )
        findings = evaluate_rules(engagement, settings_obj)
        assert "convergence_stall" not in _rule_names(findings)

    def test_does_not_fire_when_no_open_defects(self, engagement, source):
        settings_obj = _settings(engagement)
        Ticket.objects.create(
            source=source, external_id="1", summary="d1", ticket_type="Bug",
            is_done=True, source_created_at=timezone.now() - timedelta(days=20),
            closed_at=timezone.now() - timedelta(days=19),
        )
        findings = evaluate_rules(engagement, settings_obj)
        assert "convergence_stall" not in _rule_names(findings)

    def test_does_not_fire_with_less_than_two_weeks_of_data(self, engagement, source):
        settings_obj = _settings(engagement)
        Ticket.objects.create(
            source=source, external_id="1", summary="d1", ticket_type="Bug",
            is_done=False, source_created_at=timezone.now(),
        )
        findings = evaluate_rules(engagement, settings_obj)
        assert "convergence_stall" not in _rule_names(findings)

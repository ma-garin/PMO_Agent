from datetime import date, timedelta
from unittest.mock import patch

import pytest
from django.contrib.auth.models import User
from django.utils import timezone

from analytics import services
from analytics.models import WeeklyDigest
from engagements.models import Engagement
from llm.providers.base import LlmError
from tickets.models import Notification, Ticket, TicketSource


@pytest.fixture
def engagement(db) -> Engagement:
    owner = User.objects.create_user(username="pmo", password="x")
    return Engagement.objects.create(name="検証案件", owner=owner)


@pytest.fixture
def source(engagement) -> TicketSource:
    return TicketSource.objects.create(
        engagement=engagement,
        kind=TicketSource.Kind.JIRA,
        name="テストJIRA",
        base_url="https://example.atlassian.net",
        project_key="T",
    )


WEEK_START = date(2026, 7, 6)  # 月曜


def _dt_on(day_offset: int):
    return timezone.make_aware(
        timezone.datetime.combine(WEEK_START + timedelta(days=day_offset), timezone.datetime.min.time())
    )


@pytest.mark.django_db
class TestWeeklyDigestMetrics:
    def test_counts_new_and_closed_within_week_boundary(self, source):
        Ticket.objects.create(
            source=source,
            external_id="1",
            summary="新規欠陥",
            ticket_type="Bug",
            source_created_at=_dt_on(2),
        )
        Ticket.objects.create(
            source=source,
            external_id="2",
            summary="クローズ済み",
            ticket_type="Bug",
            is_done=True,
            source_created_at=_dt_on(0) - timedelta(days=30),
            closed_at=_dt_on(3),
        )
        # 週の範囲外の欠陥は集計されない
        Ticket.objects.create(
            source=source,
            external_id="3",
            summary="先週の欠陥",
            ticket_type="Bug",
            source_created_at=_dt_on(-1),
        )

        metrics = services.weekly_digest_metrics(source.engagement, WEEK_START)
        assert metrics["new_defects"] == 1
        assert metrics["closed_defects"] == 1

    def test_progress_change_reflects_closures_during_week(self, source):
        Ticket.objects.create(
            source=source, external_id="1", summary="a", is_done=True, closed_at=_dt_on(0) - timedelta(days=30)
        )
        Ticket.objects.create(source=source, external_id="2", summary="b", is_done=True, closed_at=_dt_on(3))
        Ticket.objects.create(source=source, external_id="3", summary="c", is_done=False)
        Ticket.objects.create(source=source, external_id="4", summary="d", is_done=False)

        metrics = services.weekly_digest_metrics(source.engagement, WEEK_START)
        # 週開始時点で1/4=25%、週末時点で2/4=50%
        assert metrics["progress_percent"] == 50
        assert metrics["progress_change"] == 25


@pytest.mark.django_db
class TestGenerateWeeklyDigest:
    def test_llm_success_stores_body_and_metrics(self, source):
        with patch("analytics.services.run_completion", return_value="順調に進捗しています。"):
            digest = services.generate_weekly_digest(source.engagement, week_start=WEEK_START)

        assert digest.body == "順調に進捗しています。"
        assert digest.week_start == WEEK_START
        assert digest.metrics["week_start"] == WEEK_START.isoformat()

    def test_llm_failure_falls_back_to_template(self, source):
        with patch("analytics.services.run_completion", side_effect=LlmError("down")):
            digest = services.generate_weekly_digest(source.engagement, week_start=WEEK_START)

        assert "新規欠陥" in digest.body
        assert "進捗率は" in digest.body

    def test_running_twice_for_same_week_overwrites_not_duplicates(self, source):
        with patch("analytics.services.run_completion", return_value="1回目"):
            services.generate_weekly_digest(source.engagement, week_start=WEEK_START)
        with patch("analytics.services.run_completion", return_value="2回目"):
            services.generate_weekly_digest(source.engagement, week_start=WEEK_START)

        digests = WeeklyDigest.objects.filter(engagement=source.engagement, week_start=WEEK_START)
        assert digests.count() == 1
        assert digests.first().body == "2回目"

    def test_new_notification_counted_in_metrics(self, source):
        ticket = Ticket.objects.create(source=source, external_id="1", summary="a")
        notification = Notification.objects.create(
            engagement=source.engagement, ticket=ticket, kind=Notification.Kind.STAGNANT, message="停滞"
        )
        notification.created_at = _dt_on(2)
        notification.save(update_fields=["created_at"])

        metrics = services.weekly_digest_metrics(source.engagement, WEEK_START)
        assert metrics["new_notifications"] == 1

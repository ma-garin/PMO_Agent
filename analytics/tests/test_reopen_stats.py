from datetime import datetime, timezone as dt_timezone

import pytest
from django.contrib.auth.models import User

from analytics import services
from engagements.models import Engagement
from tickets.models import Ticket, TicketSource, TicketStatusTransition


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


def _dt(day: int) -> datetime:
    return datetime(2026, 6, day, tzinfo=dt_timezone.utc)


@pytest.mark.django_db
class TestReopenStats:
    def test_never_closed_ticket_not_counted(self, source):
        Ticket.objects.create(source=source, external_id="1", summary="a")
        stats = services.reopen_stats(source.engagement)
        assert stats == {"reopened_count": 0, "closed_count": 0, "reopen_rate": 0.0}

    def test_closed_once_and_never_reopened(self, source):
        ticket = Ticket.objects.create(source=source, external_id="1", summary="a")
        TicketStatusTransition.objects.create(
            ticket=ticket, from_status="進行中", to_status="完了", occurred_at=_dt(1)
        )
        stats = services.reopen_stats(source.engagement)
        assert stats["closed_count"] == 1
        assert stats["reopened_count"] == 0
        assert stats["reopen_rate"] == 0.0

    def test_closed_then_reopened_counts_as_reopened(self, source):
        ticket = Ticket.objects.create(source=source, external_id="1", summary="a")
        TicketStatusTransition.objects.create(
            ticket=ticket, from_status="進行中", to_status="完了", occurred_at=_dt(1)
        )
        TicketStatusTransition.objects.create(
            ticket=ticket, from_status="完了", to_status="再オープン", occurred_at=_dt(2)
        )
        stats = services.reopen_stats(source.engagement)
        assert stats["closed_count"] == 1
        assert stats["reopened_count"] == 1
        assert stats["reopen_rate"] == 100.0

    def test_reopen_rate_is_percentage_of_closed_tickets(self, source):
        t1 = Ticket.objects.create(source=source, external_id="1", summary="a")
        t2 = Ticket.objects.create(source=source, external_id="2", summary="b")
        for t in (t1, t2):
            TicketStatusTransition.objects.create(
                ticket=t, from_status="進行中", to_status="完了", occurred_at=_dt(1)
            )
        TicketStatusTransition.objects.create(
            ticket=t1, from_status="完了", to_status="再オープン", occurred_at=_dt(2)
        )
        stats = services.reopen_stats(source.engagement)
        assert stats["closed_count"] == 2
        assert stats["reopened_count"] == 1
        assert stats["reopen_rate"] == 50.0

    def test_zero_closed_tickets_does_not_divide_by_zero(self, source):
        ticket = Ticket.objects.create(source=source, external_id="1", summary="a")
        TicketStatusTransition.objects.create(
            ticket=ticket, from_status="", to_status="進行中", occurred_at=_dt(1)
        )
        stats = services.reopen_stats(source.engagement)
        assert stats["reopen_rate"] == 0.0

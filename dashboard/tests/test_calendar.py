import pytest
from django.contrib.auth.models import User

from dashboard.services import month_grid
from engagements.models import Engagement
from tickets.models import Ticket, TicketSource


@pytest.fixture
def engagement(db) -> Engagement:
    owner = User.objects.create_user(username="pmo", password="x")
    return Engagement.objects.create(name="検証案件", owner=owner)


@pytest.mark.django_db
class TestMonthGrid:
    def test_month_starting_on_sunday_pads_previous_month_days(self, engagement):
        # 2026年2月1日は日曜日
        weeks = month_grid(engagement, 2026, 2)
        first_week = weeks[0]
        assert len(first_week) == 7
        assert first_week[-1]["date"].day == 1
        assert first_week[-1]["in_month"] is True
        assert first_week[0]["in_month"] is False

    def test_december_to_january_transition(self, engagement):
        weeks = month_grid(engagement, 2026, 12)
        all_days_in_month = [d for week in weeks for d in week if d["in_month"]]
        assert len(all_days_in_month) == 31

    def test_due_ticket_appears_on_correct_day(self, engagement):
        source = TicketSource.objects.create(
            engagement=engagement, kind="jira", name="s", base_url="https://x", project_key="P"
        )
        Ticket.objects.create(
            source=source, external_id="1", summary="期限チケット", due_date="2026-07-15"
        )
        weeks = month_grid(engagement, 2026, 7)
        matching_days = [
            d for week in weeks for d in week if d["date"].day == 15 and d["in_month"]
        ]
        assert len(matching_days) == 1
        assert len(matching_days[0]["tickets"]) == 1

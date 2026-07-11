from datetime import datetime, timezone as dt_timezone

import pytest
from django.contrib.auth.models import User

from analytics import services
from analytics.models import OdcClassification
from engagements.models import Engagement
from tickets.models import Ticket, TicketSource


@pytest.fixture
def owner(db) -> User:
    return User.objects.create_user(username="pmo", password="x")


def _make_confirmed(source, ext_id, defect_type, updated_at):
    ticket = Ticket.objects.create(source=source, external_id=ext_id, summary=ext_id, ticket_type="Bug")
    classification = OdcClassification.objects.create(
        ticket=ticket, defect_type=defect_type, status=OdcClassification.Status.CONFIRMED
    )
    # updated_atはauto_now=Trueのためsave()経由では上書きできない。QuerySet.update()で直接書き換える。
    OdcClassification.objects.filter(pk=classification.pk).update(updated_at=updated_at)
    return classification


@pytest.mark.django_db
class TestMonthlyOdcTrend:
    def test_groups_by_month_and_defect_type(self, owner):
        engagement = Engagement.objects.create(name="A", owner=owner)
        source = TicketSource.objects.create(
            engagement=engagement, kind="jira", name="s", base_url="https://x", project_key="P"
        )
        _make_confirmed(source, "1", "function", datetime(2026, 5, 10, tzinfo=dt_timezone.utc))
        _make_confirmed(source, "2", "checking", datetime(2026, 5, 15, tzinfo=dt_timezone.utc))
        _make_confirmed(source, "3", "function", datetime(2026, 6, 5, tzinfo=dt_timezone.utc))

        trend = services.monthly_odc_trend(engagement)
        assert [s["label"] for s in trend["series"]] == ["2026/5", "2026/6"]
        assert trend["series"][0]["by_type"] == {"function": 1, "checking": 1}
        assert trend["series"][0]["total"] == 2
        assert trend["series"][1]["by_type"] == {"function": 1}

    def test_pending_classifications_are_excluded(self, owner):
        engagement = Engagement.objects.create(name="A", owner=owner)
        source = TicketSource.objects.create(
            engagement=engagement, kind="jira", name="s", base_url="https://x", project_key="P"
        )
        ticket = Ticket.objects.create(source=source, external_id="1", summary="a", ticket_type="Bug")
        OdcClassification.objects.create(
            ticket=ticket, defect_type="function", status=OdcClassification.Status.PENDING
        )

        trend = services.monthly_odc_trend(engagement)
        assert trend["series"] == []

    def test_no_data_returns_empty_series(self, owner):
        engagement = Engagement.objects.create(name="A", owner=owner)
        trend = services.monthly_odc_trend(engagement)
        assert trend["series"] == []
        assert len(trend["defect_types"]) == 8


@pytest.mark.django_db
class TestMonthlyOdcBars:
    def test_bar_heights_scale_relative_to_max_total(self):
        trend = {
            "series": [
                {"label": "2026/5", "by_type": {"function": 4}, "total": 4},
                {"label": "2026/6", "by_type": {"function": 2}, "total": 2},
            ],
            "defect_types": [{"value": "function", "label": "機能", "color": "#4C6FFF"}],
        }
        bars = services.monthly_odc_bars(trend, width=100, height=100)
        assert len(bars) == 2
        assert bars[0]["segments"][0]["height"] == 100.0
        assert bars[1]["segments"][0]["height"] == 50.0

    def test_empty_series_returns_empty_bars(self):
        trend = {"series": [], "defect_types": []}
        assert services.monthly_odc_bars(trend) == []


@pytest.mark.django_db
class TestBenchmarkRows:
    def test_labels_are_anonymized_and_stable_within_a_call(self, owner):
        Engagement.objects.create(name="極秘案件A", owner=owner)
        Engagement.objects.create(name="極秘案件B", owner=owner)

        rows = services.benchmark_rows()

        assert [r["label"] for r in rows] == ["案件A", "案件B"]
        assert all("極秘" not in r["label"] for r in rows)

    def test_label_wraps_to_double_letters_past_26(self, owner):
        for i in range(27):
            Engagement.objects.create(name=f"e{i}", owner=owner)

        rows = services.benchmark_rows()
        assert rows[25]["label"] == "案件Z"
        assert rows[26]["label"] == "案件AA"

    def test_row_includes_defect_and_reopen_stats(self, owner):
        engagement = Engagement.objects.create(name="A", owner=owner)
        source = TicketSource.objects.create(
            engagement=engagement, kind="jira", name="s", base_url="https://x", project_key="P"
        )
        Ticket.objects.create(source=source, external_id="1", summary="a", ticket_type="Bug")

        rows = services.benchmark_rows()
        assert rows[0]["defect_total"] == 1
        assert rows[0]["reopen_rate"] == 0.0

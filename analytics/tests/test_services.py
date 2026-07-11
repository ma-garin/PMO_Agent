from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from django.utils import timezone

from analytics import services
from analytics.models import OdcClassification
from engagements.models import Engagement
from tickets.models import Ticket, TicketSource


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


def _make_ticket(source, ext_id, ticket_type, created_days_ago, closed_days_ago=None):
    now = timezone.now()
    return Ticket.objects.create(
        source=source,
        external_id=ext_id,
        summary=f"チケット{ext_id}",
        ticket_type=ticket_type,
        is_done=closed_days_ago is not None,
        source_created_at=now - timedelta(days=created_days_ago),
        source_updated_at=now - timedelta(days=closed_days_ago or 0),
        closed_at=(now - timedelta(days=closed_days_ago)) if closed_days_ago else None,
    )


@pytest.mark.django_db
class TestDefectFiltering:
    def test_default_mapping_matches_bug_variants_case_insensitively(self, source):
        _make_ticket(source, "1", "Bug", 5)
        _make_ticket(source, "2", "バグ", 5)
        _make_ticket(source, "3", "Task", 5)
        assert services.get_defects(source.engagement).count() == 2

    def test_custom_mapping_overrides_default(self, source):
        source.engagement.defect_ticket_types = ["障害"]
        source.engagement.save()
        _make_ticket(source, "1", "Bug", 5)
        _make_ticket(source, "2", "障害", 5)
        assert services.get_defects(source.engagement).count() == 1


@pytest.mark.django_db
class TestSummarize:
    def test_density_requires_size(self, source):
        _make_ticket(source, "1", "Bug", 5)
        summary = services.summarize_defects(source.engagement)
        assert summary["density"] is None

        source.engagement.size_metric_value = Decimal("100")
        source.engagement.save()
        summary = services.summarize_defects(source.engagement)
        assert summary["density"] == Decimal("0.01")

    def test_open_closed_counts(self, source):
        _make_ticket(source, "1", "Bug", 10, closed_days_ago=2)
        _make_ticket(source, "2", "Bug", 5)
        summary = services.summarize_defects(source.engagement)
        assert summary["total"] == 2
        assert summary["closed"] == 1
        assert summary["open"] == 1


@pytest.mark.django_db
class TestConvergence:
    def test_cumulative_counts_increase_over_weeks(self, source):
        _make_ticket(source, "1", "Bug", 21, closed_days_ago=14)
        _make_ticket(source, "2", "Bug", 7)
        series = services.convergence_series(source.engagement)
        assert series, "系列が空"
        assert series[-1]["opened"] == 2
        assert series[-1]["closed"] == 1
        opened_values = [p["opened"] for p in series]
        assert opened_values == sorted(opened_values), "累積は単調増加のはず"

    def test_empty_when_no_defects(self, engagement):
        assert services.convergence_series(engagement) == []


@pytest.mark.django_db
class TestOdcDistribution:
    def test_only_confirmed_classifications_counted(self, source):
        t1 = _make_ticket(source, "1", "Bug", 5)
        t2 = _make_ticket(source, "2", "Bug", 5)
        OdcClassification.objects.create(
            ticket=t1,
            defect_type=OdcClassification.DefectType.FUNCTION,
            status=OdcClassification.Status.CONFIRMED,
        )
        OdcClassification.objects.create(
            ticket=t2,
            defect_type=OdcClassification.DefectType.FUNCTION,
            status=OdcClassification.Status.PENDING,
        )
        dist = services.odc_distribution(source.engagement)
        assert dist["confirmed_count"] == 1
        assert dist["unclassified_count"] == 1
        assert dist["defect_type"][0]["count"] == 1

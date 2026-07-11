from unittest.mock import patch

import pytest
from django.contrib.auth.models import User

from engagements.models import Engagement
from risks.models import RiskItem
from risks.services import risk_matrix, suggest_risks


@pytest.fixture
def engagement(db) -> Engagement:
    owner = User.objects.create_user(username="pmo", password="x")
    return Engagement.objects.create(name="検証案件", owner=owner)


@pytest.mark.django_db
class TestRiskMatrix:
    def test_cells_group_by_probability_and_impact(self, engagement):
        RiskItem.objects.create(engagement=engagement, title="a", probability=5, impact=5)
        RiskItem.objects.create(engagement=engagement, title="b", probability=5, impact=5)
        RiskItem.objects.create(engagement=engagement, title="c", probability=1, impact=1)

        grid = risk_matrix(engagement)
        assert len(grid[(5, 5)]) == 2
        assert len(grid[(1, 1)]) == 1
        assert len(grid[(3, 3)]) == 0

    def test_closed_risks_excluded(self, engagement):
        RiskItem.objects.create(
            engagement=engagement, title="closed", probability=5, impact=5, status=RiskItem.Status.CLOSED
        )
        grid = risk_matrix(engagement)
        assert len(grid[(5, 5)]) == 0


@pytest.mark.django_db
class TestSuggestRisks:
    def test_valid_json_array_parsed(self, engagement):
        raw = (
            '[{"title": "リスクA", "description": "説明", "probability": 4, "impact": 5, '
            '"measurement": "週次モニタリング"}]'
        )
        with patch("risks.services.run_completion", return_value=raw):
            candidates = suggest_risks(engagement)
        assert len(candidates) == 1
        assert candidates[0]["title"] == "リスクA"
        assert candidates[0]["probability"] == 4

    def test_out_of_range_values_clamped(self, engagement):
        raw = '[{"title": "リスクB", "probability": 99, "impact": -3}]'
        with patch("risks.services.run_completion", return_value=raw):
            candidates = suggest_risks(engagement)
        assert candidates[0]["probability"] == 5
        assert candidates[0]["impact"] == 1

    def test_broken_json_returns_empty_list(self, engagement):
        with patch("risks.services.run_completion", return_value="not json"):
            assert suggest_risks(engagement) == []

    def test_max_five_candidates(self, engagement):
        items = [{"title": f"r{i}"} for i in range(10)]
        import json

        with patch("risks.services.run_completion", return_value=json.dumps(items)):
            candidates = suggest_risks(engagement)
        assert len(candidates) == 5

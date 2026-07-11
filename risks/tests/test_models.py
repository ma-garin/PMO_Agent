import pytest
from django.contrib.auth.models import User

from engagements.models import Engagement
from risks.models import RiskItem


@pytest.fixture
def engagement(db) -> Engagement:
    owner = User.objects.create_user(username="pmo", password="x")
    return Engagement.objects.create(name="検証案件", owner=owner)


@pytest.mark.django_db
class TestRiskScoreSeverity:
    @pytest.mark.parametrize(
        "probability,impact,expected",
        [
            (5, 5, "high"),  # 25
            (3, 5, "high"),  # 15 (境界)
            (2, 4, "medium"),  # 8 (境界)
            (4, 2, "medium"),  # 8
            (2, 3, "low"),  # 6
            (1, 1, "low"),  # 1
        ],
    )
    def test_severity_boundaries(self, engagement, probability, impact, expected):
        risk = RiskItem.objects.create(
            engagement=engagement, title="r", probability=probability, impact=impact
        )
        assert risk.score == probability * impact
        assert risk.severity == expected

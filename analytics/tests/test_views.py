import pytest
from django.contrib.auth.models import User
from django.test import Client

from engagements.models import Engagement


@pytest.fixture
def user(db) -> User:
    return User.objects.create_user(username="pmo", password="x")


@pytest.fixture
def engagement(user) -> Engagement:
    e = Engagement.objects.create(name="検証案件", owner=user)
    e.members.add(user)
    return e


@pytest.fixture
def logged_in_client(client: Client, user, engagement) -> Client:
    client.force_login(user)
    session = client.session
    session["current_engagement_id"] = engagement.pk
    session.save()
    return client


@pytest.mark.django_db
class TestAnalysisViewMonthlyTab:
    def test_analysis_page_renders_with_monthly_trend_context(self, logged_in_client):
        response = logged_in_client.get("/analytics/")
        assert response.status_code == 200
        assert "monthly_bars" in response.context
        assert "monthly_defect_types" in response.context
        assert len(response.context["monthly_defect_types"]) == 8
        assert "月次推移".encode() in response.content

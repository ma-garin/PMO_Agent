from unittest.mock import patch

import pytest
from django.contrib.auth.models import User
from django.test import Client

from engagements.models import Engagement
from llm.providers.base import LlmError
from reports.models import Report


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
class TestReportCreate:
    def test_create_generates_draft_body(self, logged_in_client):
        with patch("reports.views.generate_draft", return_value="# 品質状況報告書\n本文"):
            response = logged_in_client.post(
                "/reports/create/",
                {"title": "月次報告", "period_start": "2026-07-01", "period_end": "2026-07-31"},
            )
        report = Report.objects.get()
        assert report.body == "# 品質状況報告書\n本文"
        assert response.status_code == 302

    def test_llm_error_creates_report_with_empty_body(self, logged_in_client):
        with patch("reports.views.generate_draft", side_effect=LlmError("down")):
            logged_in_client.post(
                "/reports/create/",
                {"title": "月次報告", "period_start": "2026-07-01", "period_end": "2026-07-31"},
            )
        report = Report.objects.get()
        assert report.body == ""


@pytest.mark.django_db
class TestReportEditApprove:
    def test_save_then_approve_locks_editing(self, logged_in_client, engagement, user):
        report = Report.objects.create(
            engagement=engagement,
            title="t",
            period_start="2026-07-01",
            period_end="2026-07-31",
            created_by=user,
        )
        logged_in_client.post(f"/reports/{report.pk}/", {"action": "save", "body": "更新本文"})
        report.refresh_from_db()
        assert report.body == "更新本文"

        logged_in_client.post(f"/reports/{report.pk}/", {"action": "approve"})
        report.refresh_from_db()
        assert report.status == Report.Status.APPROVED

        logged_in_client.post(f"/reports/{report.pk}/", {"action": "save", "body": "改ざん"})
        report.refresh_from_db()
        assert report.body == "更新本文"

    def test_other_engagement_report_is_404(self, logged_in_client):
        other_owner = User.objects.create_user(username="other", password="x")
        other_engagement = Engagement.objects.create(name="他案件", owner=other_owner)
        other_report = Report.objects.create(
            engagement=other_engagement,
            title="t",
            period_start="2026-07-01",
            period_end="2026-07-31",
        )
        response = logged_in_client.get(f"/reports/{other_report.pk}/")
        assert response.status_code == 404

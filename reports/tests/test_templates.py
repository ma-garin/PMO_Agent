from unittest.mock import patch

import pytest
from django.contrib.auth.models import User
from django.test import Client

from engagements.models import Engagement
from reports import services
from reports.models import Report, ReportTemplate


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
class TestGenerateDraftTemplateSelection:
    def test_no_template_uses_default_system_constant(self, engagement):
        with patch("reports.services.run_completion", return_value="ok") as mock_run:
            services.generate_draft(engagement, "2026-07-01", "2026-07-31")
        _, kwargs = mock_run.call_args
        assert kwargs["system"] == services.DRAFT_SYSTEM

    def test_custom_template_overrides_system_prompt(self, engagement):
        template = ReportTemplate.objects.create(
            name="カスタム", system_prompt="独自の章立てで出力してください。"
        )
        with patch("reports.services.run_completion", return_value="ok") as mock_run:
            services.generate_draft(
                engagement, "2026-07-01", "2026-07-31", template=template
            )
        _, kwargs = mock_run.call_args
        assert kwargs["system"] == "独自の章立てで出力してください。"


@pytest.mark.django_db
class TestReportCreateTemplateSelection:
    def test_explicit_template_id_is_passed_to_generate_draft(self, logged_in_client):
        template = ReportTemplate.objects.create(name="カスタム", system_prompt="独自")
        with patch("reports.views.generate_draft", return_value="本文") as mock_generate:
            logged_in_client.post(
                "/reports/create/",
                {
                    "title": "月次報告",
                    "period_start": "2026-07-01",
                    "period_end": "2026-07-31",
                    "template_id": str(template.pk),
                },
            )
        _, kwargs = mock_generate.call_args
        assert kwargs["template"] == template

    def test_no_template_id_falls_back_to_default_template(self, logged_in_client):
        default_template = ReportTemplate.objects.create(
            name="既定", system_prompt="既定文言", is_default=True
        )
        ReportTemplate.objects.create(name="非既定", system_prompt="非既定文言")

        with patch("reports.views.generate_draft", return_value="本文") as mock_generate:
            logged_in_client.post(
                "/reports/create/",
                {"title": "月次報告", "period_start": "2026-07-01", "period_end": "2026-07-31"},
            )
        _, kwargs = mock_generate.call_args
        assert kwargs["template"] == default_template


@pytest.mark.django_db
class TestSeedMigration:
    def test_default_template_exists_after_migration(self):
        assert ReportTemplate.objects.filter(is_default=True).exists()
        default = ReportTemplate.objects.get(is_default=True)
        assert "# 品質状況報告書" in default.system_prompt

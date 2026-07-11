"""各記録ポイントで実際にビューを叩き、AuditLogが1行増えることを確認する。"""

from unittest.mock import patch

import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse

from analytics.models import OdcClassification
from audit.models import AuditLog
from engagements.models import Engagement
from reports.models import Report
from testmgmt.models import QualityGate, TestPlan
from tickets.models import Ticket, TicketSource


@pytest.fixture
def admin_user(db) -> User:
    return User.objects.create_user(username="admin", password="x", is_staff=True)


@pytest.fixture
def engagement(admin_user) -> Engagement:
    e = Engagement.objects.create(name="検証案件", owner=admin_user)
    e.members.add(admin_user)
    return e


@pytest.fixture
def admin_client(client: Client, admin_user, engagement) -> Client:
    client.force_login(admin_user)
    session = client.session
    session["current_engagement_id"] = engagement.pk
    session.save()
    return client


@pytest.mark.django_db
class TestTokenRecordingPoints:
    def test_token_create_records_log(self, admin_client):
        admin_client.post(
            reverse("tickets:source_settings"),
            {
                "kind": "jira",
                "name": "新規接続",
                "base_url": "https://example.atlassian.net",
                "project_key": "P",
                "username": "u@example.com",
                "api_token": "secret",
                "is_active": "on",
            },
        )
        assert AuditLog.objects.filter(action="token_create").count() == 1

    def test_token_update_records_log(self, admin_client, engagement):
        source = TicketSource.objects.create(
            engagement=engagement, kind="jira", name="s", base_url="https://x", project_key="P"
        )
        admin_client.post(
            reverse("adminpanel:tokens"),
            {"action": "update_token", "source_id": source.pk, "api_token": "newtoken"},
        )
        assert AuditLog.objects.filter(action="token_update").count() == 1

    def test_token_delete_records_log(self, admin_client, engagement):
        source = TicketSource.objects.create(
            engagement=engagement, kind="jira", name="s", base_url="https://x", project_key="P"
        )
        admin_client.post(
            reverse("adminpanel:tokens"), {"action": "delete", "source_id": source.pk}
        )
        assert AuditLog.objects.filter(action="token_delete").count() == 1


@pytest.mark.django_db
class TestEngagementRecordingPoints:
    def test_engagement_create_records_log(self, admin_client):
        admin_client.post(
            reverse("engagements:create"),
            {"name": "新規案件", "status": "active", "llm_provider": "ollama"},
        )
        assert AuditLog.objects.filter(action="engagement_create").count() == 1

    def test_engagement_edit_records_log(self, admin_client, engagement, admin_user):
        admin_client.post(
            reverse("adminpanel:engagement_edit", args=[engagement.pk]),
            {
                "name": "更新後案件",
                "status": "active",
                "llm_provider": "ollama",
                "members": [admin_user.pk],
            },
        )
        assert AuditLog.objects.filter(action="engagement_edit").count() == 1


@pytest.mark.django_db
class TestUserRecordingPoints:
    def test_user_create_records_log(self, admin_client):
        admin_client.post(
            reverse("adminpanel:users"),
            {"action": "create", "username": "newbie", "password": "pass123456789"},
        )
        assert AuditLog.objects.filter(action="user_create").count() == 1

    def test_user_permission_change_records_log(self, admin_client):
        target = User.objects.create_user(username="target", password="x")
        admin_client.post(
            reverse("adminpanel:users"), {"action": "toggle_staff", "user_id": target.pk}
        )
        assert AuditLog.objects.filter(action="user_permission_change").count() == 1

    def test_user_active_change_records_log(self, admin_client):
        target = User.objects.create_user(username="target2", password="x")
        admin_client.post(
            reverse("adminpanel:users"), {"action": "toggle_active", "user_id": target.pk}
        )
        assert AuditLog.objects.filter(action="user_active_change").count() == 1


@pytest.mark.django_db
class TestOdcConfirmRecordingPoint:
    def test_classify_ticket_records_log(self, admin_client, engagement):
        source = TicketSource.objects.create(
            engagement=engagement, kind="jira", name="s", base_url="https://x", project_key="P"
        )
        ticket = Ticket.objects.create(
            source=source, external_id="T-1", summary="欠陥", ticket_type="Bug"
        )
        admin_client.post(
            reverse("analytics:classify", args=[ticket.pk]),
            {
                "defect_type": "function",
                "trigger": "coverage",
                "activity": "unit_test",
                "impact": "major",
            },
        )
        assert AuditLog.objects.filter(action="odc_confirm").count() == 1
        assert OdcClassification.objects.get(ticket=ticket).status == "confirmed"


@pytest.mark.django_db
class TestReportApproveRecordingPoint:
    def test_report_approve_records_log(self, admin_client, engagement, admin_user):
        report = Report.objects.create(
            engagement=engagement,
            title="報告書",
            period_start="2026-07-01",
            period_end="2026-07-31",
            created_by=admin_user,
        )
        admin_client.post(reverse("reports:edit", args=[report.pk]), {"action": "approve"})
        assert AuditLog.objects.filter(action="report_approve").count() == 1


@pytest.mark.django_db
class TestTestmgmtRecordingPoints:
    def test_quality_gate_judge_records_log(self, admin_client, engagement):
        gate = QualityGate.objects.create(engagement=engagement, name="ゲート1", criteria={})
        admin_client.post(
            reverse("testmgmt:gate_detail", args=[gate.pk]),
            {"verdict": "passed", "note": "問題なし"},
        )
        assert AuditLog.objects.filter(action="quality_gate_judge").count() == 1

    def test_test_plan_approve_records_log(self, admin_client, engagement, admin_user):
        plan = TestPlan.objects.create(
            engagement=engagement, kind=TestPlan.Kind.MASTER, title="計画1", created_by=admin_user
        )
        admin_client.post(reverse("testmgmt:plan_edit", args=[plan.pk]), {"action": "approve"})
        assert AuditLog.objects.filter(action="test_plan_approve").count() == 1


@pytest.mark.django_db
class TestAuditListAccess:
    def test_general_user_cannot_view_audit_list(self, client):
        general = User.objects.create_user(username="general", password="x", is_staff=False)
        client.force_login(general)
        response = client.get(reverse("adminpanel:audit:list"))
        assert response.status_code == 302
        assert response.url == reverse("dashboard:home")

    def test_admin_can_view_audit_list(self, admin_client):
        response = admin_client.get(reverse("adminpanel:audit:list"))
        assert response.status_code == 200

    def test_action_filter_narrows_results(self, admin_client, engagement, admin_user):
        from audit.services import record

        record(admin_user, "token_update", engagement, detail="a")
        record(admin_user, "user_create", engagement, detail="b")

        response = admin_client.get(reverse("adminpanel:audit:list"), {"action": "token"})
        page_actions = [log.action for log in response.context["page_obj"]]
        assert page_actions == ["token_update"]

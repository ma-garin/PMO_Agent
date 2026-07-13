import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse

from audit.models import AuditLog
from engagements.models import Engagement

ADMIN_URLS = ["home", "engagements", "users", "llm_usage", "ai_logs", "audit"]


@pytest.fixture
def staff(db) -> User:
    return User.objects.create_user(username="admin", password="x", is_staff=True)


@pytest.fixture
def general(db) -> User:
    return User.objects.create_user(username="general", password="x")


@pytest.fixture
def engagement(staff) -> Engagement:
    e = Engagement.objects.create(name="案件X", owner=staff, progress=40)
    e.members.add(staff)
    return e


@pytest.mark.django_db
class TestAccessControl:
    @pytest.mark.parametrize("name", ADMIN_URLS)
    def test_anonymous_redirected(self, client: Client, name: str):
        resp = client.get(reverse(f"adminpanel:{name}"))
        assert resp.status_code == 302 and reverse("accounts:login") in resp.url

    @pytest.mark.parametrize("name", ADMIN_URLS)
    def test_general_user_forbidden(self, client: Client, general: User, name: str):
        client.force_login(general)
        resp = client.get(reverse(f"adminpanel:{name}"))
        # admin_required は非staffをリダイレクト(pmo_agent:home)
        assert resp.status_code == 302 and reverse("adminpanel:home") not in resp.url

    @pytest.mark.parametrize("name", ADMIN_URLS)
    def test_staff_ok(self, client: Client, staff: User, name: str):
        client.force_login(staff)
        assert client.get(reverse(f"adminpanel:{name}")).status_code == 200


@pytest.mark.django_db
class TestEngagementCrud:
    def test_edit_updates_and_audits(self, client: Client, staff: User, engagement: Engagement):
        client.force_login(staff)
        resp = client.post(
            reverse("adminpanel:engagement_edit", args=[engagement.pk]),
            {"name": "案件X改", "description": "更新", "status": "on_hold", "progress": 80, "owner": staff.pk, "members": [staff.pk]},
        )
        assert resp.status_code == 302
        engagement.refresh_from_db()
        assert engagement.name == "案件X改" and engagement.progress == 80
        assert AuditLog.objects.filter(action="engagement_edit").count() == 1

    def test_invalid_progress_rejected(self, client: Client, staff: User, engagement: Engagement):
        client.force_login(staff)
        resp = client.post(
            reverse("adminpanel:engagement_edit", args=[engagement.pk]),
            {"name": "X", "description": "", "status": "active", "progress": 150, "owner": staff.pk, "members": [staff.pk]},
        )
        assert resp.status_code == 200  # 再表示(バリデーションエラー)
        engagement.refresh_from_db()
        assert engagement.progress == 40

    def test_delete_removes_and_audits(self, client: Client, staff: User, engagement: Engagement):
        client.force_login(staff)
        resp = client.post(reverse("adminpanel:engagement_delete", args=[engagement.pk]))
        assert resp.status_code == 302
        assert not Engagement.objects.filter(pk=engagement.pk).exists()
        assert AuditLog.objects.filter(action="engagement_delete").count() == 1


@pytest.mark.django_db
class TestUsers:
    def test_toggle_staff(self, client: Client, staff: User, general: User):
        client.force_login(staff)
        client.post(reverse("adminpanel:users"), {"user_id": general.pk, "field": "is_staff"})
        general.refresh_from_db()
        assert general.is_staff is True

    def test_cannot_change_self(self, client: Client, staff: User):
        client.force_login(staff)
        client.post(reverse("adminpanel:users"), {"user_id": staff.pk, "field": "is_staff"})
        staff.refresh_from_db()
        assert staff.is_staff is True  # 変更されない

"""案件の削除機能のテスト。"""

import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from audit.models import AuditLog
from engagements.models import Engagement


@pytest.fixture
def admin_user(db) -> User:
    return User.objects.create_user(username="ap-admin", password="pass12345", is_staff=True)


@pytest.fixture
def general_user(db) -> User:
    return User.objects.create_user(username="ap-general", password="pass12345", is_staff=False)


@pytest.mark.django_db
class TestEngagementDelete:
    def test_admin_can_delete_engagement(self, client, admin_user):
        engagement = Engagement.objects.create(name="削除対象", owner=admin_user)
        client.force_login(admin_user)

        response = client.post(
            reverse("adminpanel:engagements"),
            {"action": "delete", "engagement_id": engagement.pk},
        )
        assert response.status_code == 302
        assert not Engagement.objects.filter(pk=engagement.pk).exists()

    def test_delete_is_audit_logged(self, client, admin_user):
        engagement = Engagement.objects.create(name="監査対象", owner=admin_user)
        client.force_login(admin_user)

        client.post(
            reverse("adminpanel:engagements"),
            {"action": "delete", "engagement_id": engagement.pk},
        )
        log = AuditLog.objects.filter(action="engagement_delete").first()
        assert log is not None
        assert log.detail == "監査対象"

    def test_delete_clears_session_if_current(self, client, admin_user):
        engagement = Engagement.objects.create(name="現在案件", owner=admin_user)
        client.force_login(admin_user)
        session = client.session
        session["current_engagement_id"] = engagement.pk
        session.save()

        client.post(
            reverse("adminpanel:engagements"),
            {"action": "delete", "engagement_id": engagement.pk},
        )
        assert "current_engagement_id" not in client.session

    def test_general_user_cannot_delete(self, client, general_user, admin_user):
        engagement = Engagement.objects.create(name="残る案件", owner=admin_user)
        client.force_login(general_user)

        response = client.post(
            reverse("adminpanel:engagements"),
            {"action": "delete", "engagement_id": engagement.pk},
        )
        assert response.status_code == 302
        assert response.url == reverse("dashboard:home")
        assert Engagement.objects.filter(pk=engagement.pk).exists()

    def test_archive_still_works(self, client, admin_user):
        engagement = Engagement.objects.create(name="アーカイブ対象", owner=admin_user)
        client.force_login(admin_user)

        client.post(
            reverse("adminpanel:engagements"),
            {"action": "archive", "engagement_id": engagement.pk},
        )
        engagement.refresh_from_db()
        assert engagement.status == Engagement.Status.COMPLETED

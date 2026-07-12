"""F-8: mark_notifications_read のオープンリダイレクト対策テスト。"""

import pytest
from django.test import Client
from django.urls import reverse


@pytest.fixture
def logged_in_client(client: Client, user, engagement) -> Client:
    client.force_login(user)
    session = client.session
    session["current_engagement_id"] = engagement.pk
    session.save()
    return client


@pytest.mark.django_db
class TestMarkNotificationsReadRedirect:
    def test_internal_path_is_allowed(self, logged_in_client):
        response = logged_in_client.post(
            reverse("tickets:mark_notifications_read"), {"next": "/dashboard/"}
        )
        assert response.status_code == 302
        assert response.url == "/dashboard/"

    def test_external_url_is_rejected(self, logged_in_client):
        response = logged_in_client.post(
            reverse("tickets:mark_notifications_read"), {"next": "https://evil.example.com/phish"}
        )
        assert response.status_code == 302
        assert "evil.example.com" not in response.url
        # 既定の tickets:list へフォールバック
        assert response.url == reverse("tickets:list")

    def test_protocol_relative_url_is_rejected(self, logged_in_client):
        response = logged_in_client.post(
            reverse("tickets:mark_notifications_read"), {"next": "//evil.example.com"}
        )
        assert response.status_code == 302
        assert "evil.example.com" not in response.url

    def test_missing_next_falls_back_to_default(self, logged_in_client):
        response = logged_in_client.post(reverse("tickets:mark_notifications_read"))
        assert response.status_code == 302
        assert response.url == reverse("tickets:list")

"""チケット接続設定(source_settings)の管理者限定化に関するビューテスト。"""
from __future__ import annotations

import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from engagements.models import Engagement
from tickets.models import SyncRun, TicketSource


@pytest.fixture
def admin_user(db) -> User:
    return User.objects.create_user(
        username="ts-admin", password="pass12345", is_staff=True  # noqa: S106
    )


@pytest.fixture
def general_user(db) -> User:
    return User.objects.create_user(
        username="ts-general", password="pass12345", is_staff=False  # noqa: S106
    )


@pytest.fixture
def engagement(admin_user: User, general_user: User) -> Engagement:
    engagement = Engagement.objects.create(name="トークン検証案件", owner=admin_user)
    engagement.members.add(admin_user, general_user)
    return engagement


def _select_engagement(client, engagement: Engagement) -> None:
    session = client.session
    session["current_engagement_id"] = engagement.pk
    session.save()


NEW_SOURCE_PAYLOAD = {
    "kind": TicketSource.Kind.JIRA,
    "name": "JIRA連携",
    "base_url": "https://example.atlassian.net",
    "project_key": "PROJ",
    "username": "user@example.com",
    "api_token": "secret-token-value",
}


@pytest.mark.django_db
def test_source_settings_post_forbidden_for_general_user(client, general_user, engagement) -> None:
    client.force_login(general_user)
    _select_engagement(client, engagement)

    response = client.post(reverse("tickets:source_settings"), NEW_SOURCE_PAYLOAD)

    assert response.status_code == 302
    assert TicketSource.objects.count() == 0


@pytest.mark.django_db
def test_source_settings_post_allowed_for_admin(client, admin_user, engagement) -> None:
    client.force_login(admin_user)
    _select_engagement(client, engagement)

    response = client.post(reverse("tickets:source_settings"), NEW_SOURCE_PAYLOAD)

    assert response.status_code == 302
    assert TicketSource.objects.filter(name="JIRA連携").exists()


@pytest.mark.django_db
def test_source_settings_hides_add_form_for_general_user(client, general_user, engagement) -> None:
    client.force_login(general_user)
    _select_engagement(client, engagement)

    response = client.get(reverse("tickets:source_settings"))

    assert "新しい接続を追加" not in response.content.decode()


@pytest.mark.django_db
def test_source_settings_shows_add_form_for_admin(client, admin_user, engagement) -> None:
    client.force_login(admin_user)
    _select_engagement(client, engagement)

    response = client.get(reverse("tickets:source_settings"))

    assert "新しい接続を追加" in response.content.decode()


@pytest.mark.django_db
def test_source_settings_masks_token_for_admin(client, admin_user, engagement) -> None:
    TicketSource.objects.create(
        engagement=engagement,
        kind=TicketSource.Kind.JIRA,
        name="既存接続",
        base_url="https://example.atlassian.net",
        project_key="PROJ",
        api_token="abcd1234wxyz",
    )
    client.force_login(admin_user)
    _select_engagement(client, engagement)

    response = client.get(reverse("tickets:source_settings"))
    content = response.content.decode()

    assert "****wxyz" in content
    assert "abcd1234wxyz" not in content


@pytest.mark.django_db
def test_source_settings_does_not_show_token_for_general_user(
    client, general_user, engagement
) -> None:
    TicketSource.objects.create(
        engagement=engagement,
        kind=TicketSource.Kind.JIRA,
        name="既存接続",
        base_url="https://example.atlassian.net",
        project_key="PROJ",
        api_token="abcd1234wxyz",
    )
    client.force_login(general_user)
    _select_engagement(client, engagement)

    response = client.get(reverse("tickets:source_settings"))
    content = response.content.decode()

    assert "****wxyz" not in content
    assert "abcd1234wxyz" not in content


@pytest.mark.django_db
def test_sync_source_now_allowed_for_general_user(
    client, general_user, engagement, monkeypatch
) -> None:
    source = TicketSource.objects.create(
        engagement=engagement,
        kind=TicketSource.Kind.JIRA,
        name="既存接続",
        base_url="https://example.atlassian.net",
        project_key="PROJ",
        api_token="abcd1234wxyz",
    )

    def _fake_sync(target_source: TicketSource) -> SyncRun:
        return SyncRun.objects.create(
            source=target_source, status=SyncRun.Status.SUCCESS, tickets_synced=0
        )

    monkeypatch.setattr("tickets.views.sync_ticket_source", _fake_sync)
    client.force_login(general_user)
    _select_engagement(client, engagement)

    response = client.post(reverse("tickets:sync_source", args=[source.pk]))

    assert response.status_code == 302
    assert response.url == reverse("tickets:source_settings")

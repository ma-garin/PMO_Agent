"""管理セクション(adminpanel)のビューテスト。

URL/POSTパラメータの契約:
- 全ビューは admin_required(is_staff=True)でガードされる
- adminpanel:users        GET一覧 / POST action=create|toggle_staff|toggle_active
- adminpanel:engagements  GET一覧 / POST action=archive
- adminpanel:engagement_edit(pk) GET編集フォーム / POST name/description/status + members(複数値)
- adminpanel:tokens       GET一覧 / POST action=update_token|toggle_active|delete
- adminpanel:llm_logs     GETのみ(Phase3未実装のため空表示でよい)
"""
from __future__ import annotations

import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from engagements.models import Engagement
from tickets.models import TicketSource


@pytest.fixture
def admin_user(db) -> User:
    return User.objects.create_user(
        username="ap-admin", password="pass12345", is_staff=True  # noqa: S106
    )


@pytest.fixture
def general_user(db) -> User:
    return User.objects.create_user(
        username="ap-general", password="pass12345", is_staff=False  # noqa: S106
    )


@pytest.fixture
def other_engagement(admin_user: User) -> Engagement:
    return Engagement.objects.create(name="他部門案件", owner=admin_user)


# ---------------------------------------------------------------------------
# 権限ガード: 一般ユーザーは全画面からダッシュボードへ弾かれる
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_general_user_is_redirected_from_all_admin_pages(
    client, general_user, other_engagement
) -> None:
    client.force_login(general_user)
    urls = [
        reverse("adminpanel:home"),
        reverse("adminpanel:users"),
        reverse("adminpanel:engagements"),
        reverse("adminpanel:engagement_edit", args=[other_engagement.pk]),
        reverse("adminpanel:tokens"),
        reverse("adminpanel:notification_channels"),
        reverse("adminpanel:llm_logs"),
        reverse("adminpanel:audit:list"),
        reverse("adminpanel:benchmark"),
    ]

    for url in urls:
        response = client.get(url)
        assert response.status_code == 302, url
        assert response.url == reverse("dashboard:home"), url


@pytest.mark.django_db
def test_anonymous_user_is_redirected_to_login(client) -> None:
    response = client.get(reverse("adminpanel:home"))

    assert response.status_code == 302
    assert response.url == reverse("accounts:login")


# ---------------------------------------------------------------------------
# adminpanel:home
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_home_shows_counts(client, admin_user, other_engagement) -> None:
    TicketSource.objects.create(
        engagement=other_engagement,
        kind=TicketSource.Kind.JIRA,
        name="接続",
        base_url="https://example.atlassian.net",
        project_key="PROJ",
    )
    client.force_login(admin_user)

    response = client.get(reverse("adminpanel:home"))

    assert response.status_code == 200
    content = response.content.decode()
    assert str(User.objects.count()) in content
    assert str(Engagement.objects.count()) in content
    assert str(TicketSource.objects.count()) in content


# ---------------------------------------------------------------------------
# adminpanel:users
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_users_get_lists_all_users(client, admin_user, general_user) -> None:
    client.force_login(admin_user)

    response = client.get(reverse("adminpanel:users"))
    content = response.content.decode()

    assert response.status_code == 200
    assert admin_user.username in content
    assert general_user.username in content


@pytest.mark.django_db
def test_users_create_action_creates_loginable_user(client, admin_user) -> None:
    client.force_login(admin_user)

    response = client.post(
        reverse("adminpanel:users"),
        {
            "action": "create",
            "username": "new-member",
            "email": "new-member@example.com",
            "password": "pass12345",
        },
    )

    assert response.status_code == 302
    created = User.objects.get(username="new-member")
    assert created.check_password("pass12345")
    assert created.is_staff is False


@pytest.mark.django_db
def test_users_create_action_can_grant_admin(client, admin_user) -> None:
    client.force_login(admin_user)

    client.post(
        reverse("adminpanel:users"),
        {
            "action": "create",
            "username": "new-admin",
            "email": "new-admin@example.com",
            "password": "pass12345",
            "is_staff": "on",
        },
    )

    created = User.objects.get(username="new-admin")
    assert created.is_staff is True


@pytest.mark.django_db
def test_users_toggle_staff_flips_other_user(client, admin_user, general_user) -> None:
    client.force_login(admin_user)

    client.post(
        reverse("adminpanel:users"),
        {"action": "toggle_staff", "user_id": general_user.pk},
    )

    general_user.refresh_from_db()
    assert general_user.is_staff is True


@pytest.mark.django_db
def test_users_cannot_remove_own_admin_rights(client, admin_user) -> None:
    client.force_login(admin_user)

    response = client.post(
        reverse("adminpanel:users"),
        {"action": "toggle_staff", "user_id": admin_user.pk},
    )

    admin_user.refresh_from_db()
    assert response.status_code == 302
    assert admin_user.is_staff is True


@pytest.mark.django_db
def test_users_toggle_active_flips_other_user(client, admin_user, general_user) -> None:
    client.force_login(admin_user)

    client.post(
        reverse("adminpanel:users"),
        {"action": "toggle_active", "user_id": general_user.pk},
    )

    general_user.refresh_from_db()
    assert general_user.is_active is False


# ---------------------------------------------------------------------------
# adminpanel:engagements
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_engagements_get_lists_engagements_regardless_of_membership(
    client, admin_user, other_engagement
) -> None:
    client.force_login(admin_user)

    response = client.get(reverse("adminpanel:engagements"))

    assert response.status_code == 200
    assert other_engagement.name in response.content.decode()


@pytest.mark.django_db
def test_engagements_archive_action_sets_status_completed(
    client, admin_user, other_engagement
) -> None:
    client.force_login(admin_user)

    response = client.post(
        reverse("adminpanel:engagements"),
        {"action": "archive", "engagement_id": other_engagement.pk},
    )

    other_engagement.refresh_from_db()
    assert response.status_code == 302
    assert other_engagement.status == Engagement.Status.COMPLETED


# ---------------------------------------------------------------------------
# adminpanel:engagement_edit
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_engagement_edit_get_shows_form(client, admin_user, other_engagement) -> None:
    client.force_login(admin_user)

    response = client.get(
        reverse("adminpanel:engagement_edit", args=[other_engagement.pk])
    )

    assert response.status_code == 200
    assert other_engagement.name in response.content.decode()


@pytest.mark.django_db
def test_engagement_edit_post_updates_fields_and_members(
    client, admin_user, general_user, other_engagement
) -> None:
    client.force_login(admin_user)

    response = client.post(
        reverse("adminpanel:engagement_edit", args=[other_engagement.pk]),
        {
            "name": "更新後の案件名",
            "description": "更新後の概要",
            "status": Engagement.Status.ON_HOLD,
            "members": [str(general_user.pk)],
        },
    )

    other_engagement.refresh_from_db()
    assert response.status_code == 302
    assert other_engagement.name == "更新後の案件名"
    assert other_engagement.status == Engagement.Status.ON_HOLD
    assert list(other_engagement.members.all()) == [general_user]


@pytest.mark.django_db
def test_engagement_edit_post_can_clear_all_members(
    client, admin_user, other_engagement
) -> None:
    other_engagement.members.add(admin_user)
    client.force_login(admin_user)

    client.post(
        reverse("adminpanel:engagement_edit", args=[other_engagement.pk]),
        {
            "name": other_engagement.name,
            "description": "",
            "status": Engagement.Status.ACTIVE,
        },
    )

    other_engagement.refresh_from_db()
    assert other_engagement.members.count() == 0


# ---------------------------------------------------------------------------
# adminpanel:tokens
# ---------------------------------------------------------------------------


@pytest.fixture
def source(other_engagement: Engagement) -> TicketSource:
    return TicketSource.objects.create(
        engagement=other_engagement,
        kind=TicketSource.Kind.JIRA,
        name="既存接続",
        base_url="https://example.atlassian.net",
        project_key="PROJ",
        api_token="abcd1234wxyz",
    )


@pytest.mark.django_db
def test_tokens_get_lists_sources_with_masked_token(
    client, admin_user, source: TicketSource
) -> None:
    client.force_login(admin_user)

    response = client.get(reverse("adminpanel:tokens"))
    content = response.content.decode()

    assert response.status_code == 200
    assert "****wxyz" in content
    assert "abcd1234wxyz" not in content


@pytest.mark.django_db
def test_tokens_update_with_blank_value_keeps_existing_token(
    client, admin_user, source: TicketSource
) -> None:
    client.force_login(admin_user)

    client.post(
        reverse("adminpanel:tokens"),
        {"action": "update_token", "source_id": source.pk, "api_token": ""},
    )

    source.refresh_from_db()
    assert source.api_token == "abcd1234wxyz"


@pytest.mark.django_db
def test_tokens_update_with_new_value_replaces_token(
    client, admin_user, source: TicketSource
) -> None:
    client.force_login(admin_user)

    client.post(
        reverse("adminpanel:tokens"),
        {"action": "update_token", "source_id": source.pk, "api_token": "new-secret-value"},
    )

    source.refresh_from_db()
    assert source.api_token == "new-secret-value"


@pytest.mark.django_db
def test_tokens_toggle_active_flips_flag(client, admin_user, source: TicketSource) -> None:
    client.force_login(admin_user)

    client.post(
        reverse("adminpanel:tokens"),
        {"action": "toggle_active", "source_id": source.pk},
    )

    source.refresh_from_db()
    assert source.is_active is False


@pytest.mark.django_db
def test_tokens_delete_removes_source(client, admin_user, source: TicketSource) -> None:
    client.force_login(admin_user)

    response = client.post(
        reverse("adminpanel:tokens"),
        {"action": "delete", "source_id": source.pk},
    )

    assert response.status_code == 302
    assert not TicketSource.objects.filter(pk=source.pk).exists()


# ---------------------------------------------------------------------------
# adminpanel:llm_logs (Phase 3未実装なので空表示のみ確認)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_llm_logs_get_renders_without_error(client, admin_user) -> None:
    client.force_login(admin_user)

    response = client.get(reverse("adminpanel:llm_logs"))

    assert response.status_code == 200


# ---------------------------------------------------------------------------
# adminpanel:benchmark (案件間比較、匿名化ラベル)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_benchmark_hides_real_engagement_names(client, admin_user) -> None:
    Engagement.objects.create(name="極秘プロジェクト", owner=admin_user)
    client.force_login(admin_user)

    response = client.get(reverse("adminpanel:benchmark"))

    assert response.status_code == 200
    assert "極秘プロジェクト".encode() not in response.content
    assert "案件A".encode() in response.content

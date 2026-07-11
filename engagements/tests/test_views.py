"""案件作成の管理者限定化に関するビューテスト。"""
from __future__ import annotations

import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from engagements.models import Engagement


@pytest.fixture
def general_user(db) -> User:
    return User.objects.create_user(
        username="eng-general", password="pass12345", is_staff=False  # noqa: S106
    )


@pytest.fixture
def admin_user(db) -> User:
    return User.objects.create_user(
        username="eng-admin", password="pass12345", is_staff=True  # noqa: S106
    )


@pytest.mark.django_db
def test_create_get_forbidden_for_general_user(client, general_user) -> None:
    client.force_login(general_user)

    response = client.get(reverse("engagements:create"))

    assert response.status_code == 302
    assert response.url == reverse("dashboard:home")


@pytest.mark.django_db
def test_create_post_forbidden_for_general_user(client, general_user) -> None:
    client.force_login(general_user)

    response = client.post(
        reverse("engagements:create"),
        {"name": "新規案件", "description": "", "status": Engagement.Status.ACTIVE},
    )

    assert response.status_code == 302
    assert response.url == reverse("dashboard:home")
    assert Engagement.objects.count() == 0


@pytest.mark.django_db
def test_create_get_allowed_for_admin(client, admin_user) -> None:
    client.force_login(admin_user)

    response = client.get(reverse("engagements:create"))

    assert response.status_code == 200


@pytest.mark.django_db
def test_create_post_allowed_for_admin(client, admin_user) -> None:
    client.force_login(admin_user)

    response = client.post(
        reverse("engagements:create"),
        {"name": "新規案件", "description": "", "status": Engagement.Status.ACTIVE},
    )

    assert response.status_code == 302
    engagement = Engagement.objects.get(name="新規案件")
    assert engagement.owner == admin_user
    assert admin_user in engagement.members.all()


@pytest.mark.django_db
def test_select_page_hides_create_link_for_general_user(client, general_user) -> None:
    client.force_login(general_user)

    response = client.get(reverse("engagements:select"))

    assert reverse("engagements:create") not in response.content.decode()


@pytest.mark.django_db
def test_select_page_shows_create_link_for_admin(client, admin_user) -> None:
    client.force_login(admin_user)

    response = client.get(reverse("engagements:select"))

    assert reverse("engagements:create") in response.content.decode()

"""サイドバーの管理メニューリンクは管理者にのみ表示される。"""
from __future__ import annotations

import pytest
from django.contrib.auth.models import User
from django.urls import reverse


@pytest.fixture
def general_user(db) -> User:
    return User.objects.create_user(
        username="link-general", password="pass12345", is_staff=False  # noqa: S106
    )


@pytest.fixture
def admin_user(db) -> User:
    return User.objects.create_user(
        username="link-admin", password="pass12345", is_staff=True  # noqa: S106
    )


@pytest.mark.django_db
def test_sidebar_hides_admin_link_for_general_user(client, general_user) -> None:
    client.force_login(general_user)

    response = client.get(reverse("accounts:profile"))

    assert reverse("adminpanel:home") not in response.content.decode()


@pytest.mark.django_db
def test_sidebar_shows_admin_link_for_admin_user(client, admin_user) -> None:
    client.force_login(admin_user)

    response = client.get(reverse("accounts:profile"))

    assert reverse("adminpanel:home") in response.content.decode()

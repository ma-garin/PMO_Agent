import re

import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse

from engagements.models import Engagement


@pytest.fixture
def user(db) -> User:
    return User.objects.create_user(username="pmo", password="x")


@pytest.fixture
def engagement(user) -> Engagement:
    e = Engagement.objects.create(
        name="POSレジ刷新<検証>", description="POS更改の第三者検証", progress=42, owner=user
    )
    e.members.add(user)
    return e


def _select(client: Client, engagement: Engagement) -> None:
    session = client.session
    session["current_engagement_id"] = engagement.pk
    session.save()


@pytest.mark.django_db
def test_pmo_agent_requires_login(client: Client):
    resp = client.get(reverse("pmo_agent:home"))
    assert resp.status_code == 302
    assert reverse("accounts:login") in resp.url


@pytest.mark.django_db
def test_pmo_agent_redirects_to_select_without_engagement(client: Client, user: User):
    client.force_login(user)
    resp = client.get(reverse("pmo_agent:home"))
    assert resp.status_code == 302
    assert resp.url == reverse("engagements:select")


@pytest.mark.django_db
def test_pmo_agent_injects_engagement_data(client: Client, user: User, engagement: Engagement):
    client.force_login(user)
    _select(client, engagement)

    resp = client.get(reverse("pmo_agent:home"))

    assert resp.status_code == 200
    body = resp.content.decode("utf-8")
    # 案件名はエスケープ済みで注入される
    assert "POSレジ刷新&lt;検証&gt;" in body
    assert "POSレジ刷新<検証>" not in body
    # 進捗・状態・案件別タスクstoreキーが実値になる
    assert ">42<" in body or "42" in body
    assert "進行中" in body
    assert f"engagement-{engagement.pk}" in body
    # トークン残留・verbatim残留がない(JS内の文字列リテラル '__PROJECT_' 判定は除く)
    assert re.search(r"__PROJECT_[A-Z_]+__", body) is None
    assert "{% verbatim %}" not in body
    # ヘッダー右端: ユーザーメニュー(ログアウト/アカウント設定/案件切替)・テーマ切替・ヘルプ導線
    assert reverse("accounts:logout") in body
    assert reverse("accounts:profile") in body
    assert reverse("engagements:select") in body
    assert 'id="pmoThemeToggle"' in body
    assert 'id="pmoInfoBtn"' in body
    assert "csrfmiddlewaretoken" in body


@pytest.mark.django_db
def test_pmo_agent_denies_engagement_without_membership(client: Client, user: User):
    outsider = User.objects.create_user(username="outsider", password="x")
    other = Engagement.objects.create(name="他社案件", owner=outsider)
    client.force_login(user)
    _select(client, other)

    resp = client.get(reverse("pmo_agent:home"))

    assert resp.status_code == 302
    assert resp.url == reverse("engagements:select")

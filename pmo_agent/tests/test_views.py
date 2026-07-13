import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse


@pytest.fixture
def user(db) -> User:
    return User.objects.create_user(username="pmo", password="x")


@pytest.mark.django_db
def test_pmo_agent_requires_login(client: Client):
    resp = client.get(reverse("pmo_agent:home"))
    assert resp.status_code == 302
    assert reverse("accounts:login") in resp.url


@pytest.mark.django_db
def test_pmo_agent_renders_mvp_for_authenticated_user(client: Client, user: User):
    client.force_login(user)
    resp = client.get(reverse("pmo_agent:home"))
    assert resp.status_code == 200
    body = resp.content.decode("utf-8")
    # MVPシェルが忠実に配信されていることを確認する目印。
    assert "VeriRAG PMO Agent" in body
    # verbatimラッパーはレンダリング後に残ってはならない。
    assert "{% verbatim %}" not in body
    assert "{% endverbatim %}" not in body

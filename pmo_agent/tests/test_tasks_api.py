import json

import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse

from engagements.models import Engagement
from pmo_agent.models import PmoTaskStore


@pytest.fixture
def user(db) -> User:
    return User.objects.create_user(username="pmo", password="x")


@pytest.fixture
def engagement(user) -> Engagement:
    e = Engagement.objects.create(name="検証案件", owner=user)
    e.members.add(user)
    return e


@pytest.fixture
def api_client(client: Client, user: User, engagement: Engagement) -> Client:
    client.force_login(user)
    session = client.session
    session["current_engagement_id"] = engagement.pk
    session.save()
    return client


def _post(client: Client, body: dict):
    return client.post(
        reverse("pmo_agent:tasks_api"), json.dumps(body), content_type="application/json"
    )


TASK = {"id": "WBS-001", "name": "結合試験", "owner": "PMO", "status": "in_progress", "progress": 40}


@pytest.mark.django_db
class TestTasksApi:
    def test_get_requires_engagement(self, client: Client, user: User):
        client.force_login(user)
        resp = client.get(reverse("pmo_agent:tasks_api"))
        assert resp.status_code == 403

    def test_get_empty_store(self, api_client: Client):
        resp = api_client.get(reverse("pmo_agent:tasks_api"))
        assert resp.status_code == 200
        data = resp.json()
        assert data["tasks"] == []
        assert data["savedAt"] == ""

    def test_post_saves_and_get_returns(self, api_client: Client, engagement: Engagement):
        resp = _post(api_client, {"action": "create", "tasks": [TASK], "storeHash": "abc"})
        assert resp.status_code == 200
        saved = resp.json()
        assert saved["ok"] is True and saved["savedAt"]

        data = api_client.get(reverse("pmo_agent:tasks_api")).json()
        assert data["tasks"] == [TASK]
        assert data["storeHash"] == "abc"

        store = PmoTaskStore.objects.get(engagement=engagement)
        assert store.tasks == [TASK]
        assert store.updated_by.username == "pmo"

    def test_post_rejects_non_list(self, api_client: Client):
        assert _post(api_client, {"tasks": {"id": "x"}}).status_code == 400
        assert _post(api_client, {"tasks": ["not-a-dict"]}).status_code == 400

    def test_post_conflict_on_stale_base_hash(self, api_client: Client, engagement: Engagement):
        _post(api_client, {"tasks": [TASK], "storeHash": "hash-v1"})
        resp = _post(
            api_client,
            {"tasks": [], "storeHash": "hash-v2", "baseStoreHash": "stale-hash"},
        )
        assert resp.status_code == 409
        # 競合時は保存されない
        assert PmoTaskStore.objects.get(engagement=engagement).tasks == [TASK]

    def test_post_accepts_matching_base_hash(self, api_client: Client, engagement: Engagement):
        _post(api_client, {"tasks": [TASK], "storeHash": "hash-v1"})
        resp = _post(
            api_client,
            {"tasks": [TASK, {"id": "WBS-002", "name": "追加"}], "storeHash": "hash-v2", "baseStoreHash": "hash-v1"},
        )
        assert resp.status_code == 200
        assert len(PmoTaskStore.objects.get(engagement=engagement).tasks) == 2

    def test_denied_for_non_member_engagement(self, client: Client, user: User):
        outsider = User.objects.create_user(username="outsider", password="x")
        other = Engagement.objects.create(name="他社案件", owner=outsider)
        client.force_login(user)
        session = client.session
        session["current_engagement_id"] = other.pk
        session.save()
        assert client.get(reverse("pmo_agent:tasks_api")).status_code == 403


@pytest.mark.django_db
def test_home_injects_server_tasks(api_client: Client, engagement: Engagement):
    PmoTaskStore.objects.create(
        engagement=engagement,
        tasks=[{"id": "WBS-010", "name": "サーバー保存タスク<検証>"}],
        saved_at="2026-07-13T00:00:00+00:00",
        store_hash="server-hash",
    )
    body = api_client.get(reverse("pmo_agent:home")).content.decode("utf-8")
    # JSONは<をエスケープして<script>内に注入される
    assert "サーバー保存タスク\\u003c検証>" in body
    assert "const pmoUseDemoData = false;" in body
    assert "server-hash" in body
    assert "__PMO_" not in body  # トークン残留なし

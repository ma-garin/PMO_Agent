import json

import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse

from audit.models import AuditLog
from engagements.models import Engagement
from pmo_agent.models import PmoJsonStore


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


def _url(kind: str) -> str:
    return reverse("pmo_agent:stores_api", args=[kind])


def _post(client: Client, kind: str, body: dict):
    return client.post(_url(kind), json.dumps(body), content_type="application/json")


@pytest.mark.django_db
class TestStoresApi:
    @pytest.mark.parametrize("kind", ["report", "kpi", "proposal"])
    def test_roundtrip(self, api_client: Client, engagement: Engagement, kind: str):
        payload = {"action": "save", "foo": [1, 2, 3], "nested": {"a": 1}}
        resp = _post(api_client, kind, payload)
        assert resp.status_code == 200 and resp.json()["ok"] is True

        data = api_client.get(_url(kind)).json()
        assert data["payload"] == payload
        assert data["savedAt"]

        store = PmoJsonStore.objects.get(engagement=engagement, kind=kind)
        assert store.updated_by.username == "pmo"
        # 保存のたびに監査ログが残る
        assert AuditLog.objects.filter(action=f"pmo_{kind}_store_save").count() == 1

    def test_unknown_kind_404(self, api_client: Client):
        assert api_client.get(_url("bogus")).status_code == 404
        assert _post(api_client, "bogus", {}).status_code == 404

    def test_requires_engagement(self, client: Client, user: User):
        client.force_login(user)
        assert client.get(_url("report")).status_code == 403

    def test_rejects_non_dict(self, api_client: Client):
        resp = api_client.post(_url("kpi"), json.dumps([1, 2]), content_type="application/json")
        assert resp.status_code == 400

    def test_denied_for_non_member(self, client: Client, user: User):
        outsider = User.objects.create_user(username="outsider", password="x")
        other = Engagement.objects.create(name="他社案件", owner=outsider)
        client.force_login(user)
        session = client.session
        session["current_engagement_id"] = other.pk
        session.save()
        assert client.get(_url("report")).status_code == 403

    def test_last_write_wins_but_audits_each(self, api_client: Client, engagement: Engagement):
        _post(api_client, "report", {"v": 1})
        _post(api_client, "report", {"v": 2})
        assert PmoJsonStore.objects.get(engagement=engagement, kind="report").payload == {"v": 2}
        assert AuditLog.objects.filter(action="pmo_report_store_save").count() == 2


@pytest.mark.django_db
def test_home_injects_stores(api_client: Client, engagement: Engagement):
    PmoJsonStore.objects.create(
        engagement=engagement,
        kind="report",
        payload={"selected_type": "weekly", "reports": {"weekly": {"title": "検証:週次"}}},
        saved_at="2026-07-13T00:00:00+00:00",
    )
    body = api_client.get(reverse("pmo_agent:home")).content.decode("utf-8")
    assert "検証:週次" in body
    assert "const pmoReportInjected = {" in body
    assert "__PMO_" not in body
    # storesBaseはスラッシュ二重化せず末尾/で終わる(${base}${kind}/ が正しいURLになる)
    assert "storesBase:'/pmo-agent/api/stores/'" in body

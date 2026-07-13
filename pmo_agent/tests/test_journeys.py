"""システム/受入相当のジャーニーテスト(HTTP層、ブラウザ非依存)。

今回の手動Playwright検証を回帰保証として自動化する。
"""

import json
from unittest.mock import patch

import pytest
from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import Client
from django.urls import reverse

from engagements.models import Engagement
from pmo_agent.models import PmoJsonStore, PmoTaskStore


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()
    yield


def _make_user_engagement(name: str, username: str):
    user = User.objects.create_user(username=username, password="x")
    eng = Engagement.objects.create(name=name, owner=user, progress=55)
    eng.members.add(user)
    return user, eng


def _enter(client: Client, user: User, engagement: Engagement):
    client.force_login(user)
    session = client.session
    session["current_engagement_id"] = engagement.pk
    session.save()


@pytest.mark.django_db
def test_full_login_to_pmo_agent_journey(client: Client):
    user, eng = _make_user_engagement("受入案件<検証>", "pmo")

    # 未ログインはログインへ
    resp = client.get(reverse("pmo_agent:home"))
    assert resp.status_code == 302 and reverse("accounts:login") in resp.url

    # ログイン→案件選択が見える
    client.force_login(user)
    assert client.get(reverse("engagements:select")).status_code == 200

    # 案件enter→pmo-agentへ着地
    resp = client.get(reverse("engagements:enter", args=[eng.pk]))
    assert resp.status_code == 302 and resp.url == reverse("pmo_agent:home")

    # homeに実案件名(エスケープ済)とデモOFFが載る
    body = client.get(reverse("pmo_agent:home")).content.decode("utf-8")
    assert "受入案件&lt;検証&gt;" in body
    assert "const pmoUseDemoData = false;" in body


@pytest.mark.django_db
def test_task_persist_and_reload_journey(client: Client):
    user, eng = _make_user_engagement("案件A", "pmo")
    _enter(client, user, eng)
    task = {"id": "WBS-001", "name": "結合試験", "owner": "PMO", "status": "in_progress", "delay": 2}

    # 保存→DB→home注入で復元
    assert client.post(
        reverse("pmo_agent:tasks_api"),
        json.dumps({"tasks": [task], "storeHash": "h1"}),
        content_type="application/json",
    ).status_code == 200
    assert PmoTaskStore.objects.get(engagement=eng).tasks == [task]
    body = client.get(reverse("pmo_agent:home")).content.decode("utf-8")
    assert "WBS-001" in body

    # 案件選択カードの集計(残1/遅延1)へ反映
    select = client.get(reverse("engagements:select")).content.decode("utf-8")
    assert "残 1" in select and "遅延 1" in select


@pytest.mark.django_db
def test_tenant_isolation_journey(client: Client):
    user_a, eng_a = _make_user_engagement("A社", "usera")
    user_b, eng_b = _make_user_engagement("B社", "userb")
    _enter(client, user_a, eng_a)
    client.post(
        reverse("pmo_agent:tasks_api"),
        json.dumps({"tasks": [{"id": "A-1", "name": "A社タスク"}]}),
        content_type="application/json",
    )
    # user_b は user_a の案件を選べない(403)、自分の案件は空
    _enter(client, user_b, eng_a)  # 非メンバー案件をセッションに入れても
    assert client.get(reverse("pmo_agent:tasks_api")).status_code == 403
    _enter(client, user_b, eng_b)
    assert client.get(reverse("pmo_agent:tasks_api")).json()["tasks"] == []


@pytest.mark.django_db
def test_xss_task_name_is_escaped_in_home(client: Client):
    user, eng = _make_user_engagement("案件", "pmo")
    _enter(client, user, eng)
    client.post(
        reverse("pmo_agent:tasks_api"),
        json.dumps({"tasks": [{"id": "X", "name": "<script>alert(1)</script>"}]}),
        content_type="application/json",
    )
    body = client.get(reverse("pmo_agent:home")).content.decode("utf-8")
    # データ由来の生の</script>でscript要素をbreakoutできない(<を<へ)
    assert "<script>alert(1)</script>" not in body
    assert "\\u003c/script>" in body


@pytest.mark.django_db
def test_report_approval_and_ai_run_journey(client: Client):
    user, eng = _make_user_engagement("案件", "pmo")
    _enter(client, user, eng)

    # 報告承認→サーバー永続
    client.post(
        reverse("pmo_agent:stores_api", args=["report"]),
        json.dumps({"action": "approved", "reports": {"weekly": {"approval_status": "approved"}}}),
        content_type="application/json",
    )
    store = PmoJsonStore.objects.get(engagement=eng, kind="report")
    assert store.payload["action"] == "approved"

    # AI実行(モック)→応答
    with patch("pmo_agent.views.run_completion", return_value="## 診断\n- OK"):
        data = client.post(
            reverse("pmo_agent:ai_run"),
            json.dumps({"screen": "dashboard", "action": "diagnose", "requestText": "整理して"}),
            content_type="application/json",
        ).json()
    assert data["answer"].startswith("## 診断") and data["usedFallback"] is False

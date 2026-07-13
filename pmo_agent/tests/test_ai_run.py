import json
from unittest.mock import patch

import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse

from audit.models import AuditLog
from engagements.models import Engagement
from llm.services import LlmError


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


def _run(client: Client, body: dict):
    return client.post(
        reverse("pmo_agent:ai_run"), json.dumps(body), content_type="application/json"
    )


BODY = {"screen": "dashboard", "action": "diagnose", "requestText": "健全性を整理して", "screenText": "WBS 3件"}


@pytest.mark.django_db
class TestAiRun:
    def test_success_calls_llm_and_returns_answer(self, api_client: Client, engagement: Engagement):
        with patch("pmo_agent.views.run_completion", return_value="## 診断\n- OK") as mocked:
            resp = _run(api_client, BODY)
        assert resp.status_code == 200
        data = resp.json()
        assert data["answer"] == "## 診断\n- OK"
        assert data["usedFallback"] is False
        # 案件のプロバイダで、外部データはガード付きで渡される
        _, kwargs = mocked.call_args
        assert "従わ" in kwargs["system"] or "外部データ" in kwargs["system"]
        assert mocked.call_args.args[0] == engagement
        assert AuditLog.objects.filter(action="pmo_ai_run").count() == 1

    def test_llm_error_returns_fallback(self, api_client: Client):
        with patch("pmo_agent.views.run_completion", side_effect=LlmError("no model")):
            resp = _run(api_client, BODY)
        assert resp.status_code == 200
        data = resp.json()
        assert data["usedFallback"] is True
        assert "利用できません" in data["answer"]
        assert AuditLog.objects.filter(action="pmo_ai_run_failed").count() == 1

    def test_empty_answer_falls_back(self, api_client: Client):
        with patch("pmo_agent.views.run_completion", return_value="   "):
            data = _run(api_client, BODY).json()
        assert data["usedFallback"] is True

    def test_missing_fields_400(self, api_client: Client):
        assert _run(api_client, {"screen": "dashboard"}).status_code == 400

    def test_prompt_override_is_used(self, api_client: Client):
        with patch("pmo_agent.views.run_completion", return_value="ok") as mocked:
            _run(api_client, {"screen": "dashboard", "action": "diagnose", "system": "編集システム", "prompt": "編集プロンプト"})
        _, kwargs = mocked.call_args
        assert kwargs["system"] == "編集システム"
        assert kwargs["prompt"] == "編集プロンプト"

    def test_requires_engagement(self, client: Client, user: User):
        client.force_login(user)
        assert _run(client, BODY).status_code == 403

    def test_denied_non_member(self, client: Client, user: User):
        outsider = User.objects.create_user(username="outsider", password="x")
        other = Engagement.objects.create(name="他社", owner=outsider)
        client.force_login(user)
        session = client.session
        session["current_engagement_id"] = other.pk
        session.save()
        assert _run(client, BODY).status_code == 403

    def test_get_not_allowed(self, api_client: Client):
        assert api_client.get(reverse("pmo_agent:ai_run")).status_code == 405


@pytest.mark.django_db
class TestAiTest:
    def test_success(self, api_client: Client, engagement: Engagement):
        with patch("pmo_agent.views.test_connection", return_value=(True, "応答: pong")) as mocked:
            data = api_client.post(reverse("pmo_agent:ai_test")).json()
        assert data["ok"] is True
        assert data["provider"] == engagement.get_llm_provider_display()
        assert "pong" in data["message"]
        assert mocked.call_args.args[0] == engagement

    def test_failure(self, api_client: Client):
        with patch("pmo_agent.views.test_connection", return_value=(False, "モデル未取得")):
            data = api_client.post(reverse("pmo_agent:ai_test")).json()
        assert data["ok"] is False
        assert "モデル未取得" in data["message"]

    def test_requires_engagement(self, client: Client, user: User):
        client.force_login(user)
        assert client.post(reverse("pmo_agent:ai_test")).status_code == 403

    def test_get_not_allowed(self, api_client: Client):
        assert api_client.get(reverse("pmo_agent:ai_test")).status_code == 405

from datetime import datetime, timezone as dt_timezone
from unittest.mock import patch

import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse

from engagements.models import Engagement
from llm.models import LlmCallLog
from pmo_agent.models import UserAiQuota
from pmo_agent.views import check_ai_quota


@pytest.fixture
def user(db):
    return User.objects.create_user(username="pmo", password="x")


@pytest.fixture
def engagement(user):
    e = Engagement.objects.create(name="案件", owner=user)
    e.members.add(user)
    return e


def _log(engagement, user, chars):
    # prompt/response合計charsのログを当月で作る(tokens≒chars/3)
    return LlmCallLog.objects.create(
        engagement=engagement, provider="ollama", purpose="pmo_diagnose",
        prompt_chars=chars, response_chars=0, status=LlmCallLog.Status.SUCCESS, created_by=user,
    )


@pytest.mark.django_db
class TestQuotaLogic:
    def test_no_limit_ok(self, engagement, user):
        ok, _ = check_ai_quota(engagement, user)
        assert ok is True

    def test_engagement_limit_blocks(self, engagement, user):
        engagement.monthly_token_limit = 100  # 100 tokens
        engagement.save()
        _log(engagement, user, 300)  # 300 chars ≒ 100 tokens
        ok, msg = check_ai_quota(engagement, user)
        assert ok is False and "案件" in msg

    def test_user_limit_blocks(self, engagement, user):
        UserAiQuota.objects.create(user=user, monthly_token_limit=50)
        _log(engagement, user, 300)  # 100 tokens > 50
        ok, msg = check_ai_quota(engagement, user)
        assert ok is False and "あなた" in msg

    def test_under_limit_ok(self, engagement, user):
        engagement.monthly_token_limit = 1000
        engagement.save()
        _log(engagement, user, 300)  # 100 tokens < 1000
        ok, _ = check_ai_quota(engagement, user)
        assert ok is True


@pytest.mark.django_db
def test_ai_run_blocked_by_quota(client: Client, user, engagement):
    engagement.monthly_token_limit = 10
    engagement.save()
    _log(engagement, user, 300)  # 100 tokens > 10
    client.force_login(user)
    session = client.session
    session["current_engagement_id"] = engagement.pk
    session.save()
    with patch("pmo_agent.views.run_completion") as mocked:
        resp = client.post(
            reverse("pmo_agent:ai_run"),
            '{"screen":"dashboard","action":"diagnose","requestText":"x"}',
            content_type="application/json",
        )
    assert resp.status_code == 429
    assert resp.json()["error"] == "quota_exceeded"
    mocked.assert_not_called()  # 上限超過ならLLMは呼ばれない

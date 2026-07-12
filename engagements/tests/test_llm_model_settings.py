"""LLM設定画面: モデル選択と疎通確認のテスト。"""

from unittest.mock import patch

import pytest
from django.contrib.auth.models import User

from engagements.models import Engagement
from llm.providers.base import LlmError


@pytest.fixture
def general_user(db) -> User:
    return User.objects.create_user(username="member", password="x", is_staff=False)


@pytest.fixture
def admin_user(db) -> User:
    return User.objects.create_user(username="admin", password="x", is_staff=True)


def _engagement_for(user, provider="claude") -> Engagement:
    e = Engagement.objects.create(name="案件", owner=user, llm_provider=provider)
    e.members.add(user)
    return e


def _login(client, user, engagement):
    client.force_login(user)
    session = client.session
    session["current_engagement_id"] = engagement.pk
    session.save()


@pytest.mark.django_db
class TestModelSelection:
    def test_admin_can_save_valid_model(self, client, admin_user):
        engagement = _engagement_for(admin_user, provider="claude")
        _login(client, admin_user, engagement)

        client.post(
            "/engagements/settings/llm/",
            {"action": "save", "llm_provider": "claude", "llm_model": "claude-sonnet-5"},
        )
        engagement.refresh_from_db()
        assert engagement.llm_model == "claude-sonnet-5"

    def test_invalid_model_for_cloud_provider_is_rejected(self, client, admin_user):
        engagement = _engagement_for(admin_user, provider="claude")
        _login(client, admin_user, engagement)

        client.post(
            "/engagements/settings/llm/",
            {"action": "save", "llm_provider": "claude", "llm_model": "gpt-4o"},
        )
        engagement.refresh_from_db()
        assert engagement.llm_model == ""  # 不正なので保存されない

    def test_ollama_allows_arbitrary_local_model(self, client, admin_user):
        engagement = _engagement_for(admin_user, provider="ollama")
        _login(client, admin_user, engagement)

        client.post(
            "/engagements/settings/llm/",
            {"action": "save", "llm_provider": "ollama", "llm_model": "my-custom-local:latest"},
        )
        engagement.refresh_from_db()
        assert engagement.llm_model == "my-custom-local:latest"

    def test_blank_model_falls_back_to_default(self, client, admin_user):
        engagement = _engagement_for(admin_user, provider="claude")
        engagement.llm_model = "claude-sonnet-5"
        engagement.save()
        _login(client, admin_user, engagement)

        client.post(
            "/engagements/settings/llm/",
            {"action": "save", "llm_provider": "claude", "llm_model": ""},
        )
        engagement.refresh_from_db()
        assert engagement.llm_model == ""

    def test_member_cannot_save_model(self, client, general_user):
        engagement = _engagement_for(general_user, provider="ollama")
        _login(client, general_user, engagement)

        client.post(
            "/engagements/settings/llm/",
            {"action": "save", "llm_provider": "ollama", "llm_model": "qwen2.5:7b"},
        )
        engagement.refresh_from_db()
        assert engagement.llm_model == ""


@pytest.mark.django_db
class TestConnectivityCheck:
    def test_member_can_run_connectivity_check_success(self, client, general_user):
        engagement = _engagement_for(general_user, provider="ollama")
        _login(client, general_user, engagement)

        with patch("llm.services.get_provider") as mock_get:
            mock_get.return_value.complete.return_value = "pong"
            response = client.post(
                "/engagements/settings/llm/", {"action": "test"}, follow=True
            )
        assert response.status_code == 200
        assert "疎通確認に成功".encode() in response.content

    def test_connectivity_check_reports_failure(self, client, general_user):
        engagement = _engagement_for(general_user, provider="claude")
        _login(client, general_user, engagement)

        with patch("llm.services.get_provider") as mock_get:
            mock_get.return_value.complete.side_effect = LlmError("ANTHROPIC_API_KEYが未設定です。")
            response = client.post(
                "/engagements/settings/llm/", {"action": "test"}, follow=True
            )
        assert response.status_code == 200
        assert "疎通確認に失敗".encode() in response.content

    def test_connectivity_check_does_not_send_engagement_data(self, client, general_user):
        engagement = _engagement_for(general_user, provider="ollama")
        _login(client, general_user, engagement)

        with patch("llm.services.get_provider") as mock_get:
            mock_get.return_value.complete.return_value = "pong"
            client.post("/engagements/settings/llm/", {"action": "test"})
            # 送信プロンプトは固定の "ping"(案件データを含まない)
            call = mock_get.return_value.complete.call_args
            assert call.args[0] == "ping"

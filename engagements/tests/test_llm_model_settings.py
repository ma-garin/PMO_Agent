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


@pytest.mark.django_db
class TestLlmCredentialSettings:
    def test_admin_can_set_api_key(self, client, admin_user):
        engagement = _engagement_for(admin_user, provider="openai")
        _login(client, admin_user, engagement)

        client.post(
            "/engagements/settings/llm/",
            {"action": "save", "llm_provider": "openai", "llm_model": "", "llm_api_key": "sk-new-key"},
        )
        engagement.refresh_from_db()
        assert engagement.llm_api_key == "sk-new-key"

    def test_admin_can_set_org_and_project_id(self, client, admin_user):
        engagement = _engagement_for(admin_user, provider="openai")
        _login(client, admin_user, engagement)

        client.post(
            "/engagements/settings/llm/",
            {
                "action": "save",
                "llm_provider": "openai",
                "llm_model": "",
                "llm_org_id": "org-123",
                "llm_project_id": "proj-123",
            },
        )
        engagement.refresh_from_db()
        assert engagement.llm_org_id == "org-123"
        assert engagement.llm_project_id == "proj-123"

    def test_blank_api_key_field_keeps_existing_value(self, client, admin_user):
        engagement = _engagement_for(admin_user, provider="openai")
        engagement.llm_api_key = "sk-existing"
        engagement.save()
        _login(client, admin_user, engagement)

        client.post(
            "/engagements/settings/llm/",
            {"action": "save", "llm_provider": "openai", "llm_model": "", "llm_api_key": ""},
        )
        engagement.refresh_from_db()
        assert engagement.llm_api_key == "sk-existing"

    def test_clear_checkbox_removes_api_key(self, client, admin_user):
        engagement = _engagement_for(admin_user, provider="openai")
        engagement.llm_api_key = "sk-existing"
        engagement.save()
        _login(client, admin_user, engagement)

        client.post(
            "/engagements/settings/llm/",
            {
                "action": "save",
                "llm_provider": "openai",
                "llm_model": "",
                "llm_api_key": "",
                "clear_llm_api_key": "on",
            },
        )
        engagement.refresh_from_db()
        assert engagement.llm_api_key == ""
        assert engagement.has_llm_api_key is False

    def test_member_cannot_set_api_key(self, client, general_user):
        engagement = _engagement_for(general_user, provider="openai")
        _login(client, general_user, engagement)

        client.post(
            "/engagements/settings/llm/",
            {"action": "save", "llm_provider": "openai", "llm_model": "", "llm_api_key": "sk-new-key"},
        )
        engagement.refresh_from_db()
        assert engagement.llm_api_key == ""

    def test_saved_api_key_is_never_rendered_in_response(self, client, admin_user):
        engagement = _engagement_for(admin_user, provider="openai")
        engagement.llm_api_key = "sk-super-secret-value"
        engagement.save()
        _login(client, admin_user, engagement)

        response = client.get("/engagements/settings/llm/")
        assert b"sk-super-secret-value" not in response.content

    def test_shows_configured_indicator_without_leaking_value(self, client, admin_user):
        engagement = _engagement_for(admin_user, provider="openai")
        engagement.llm_api_key = "sk-super-secret-value"
        engagement.save()
        _login(client, admin_user, engagement)

        response = client.get("/engagements/settings/llm/")
        assert "設定済み".encode() in response.content


@pytest.mark.django_db
class TestModelChoiceFiltering:
    def test_ollama_provider_does_not_render_other_provider_models(self, client, admin_user):
        engagement = _engagement_for(admin_user, provider="ollama")
        _login(client, admin_user, engagement)

        response = client.get("/engagements/settings/llm/")
        content = response.content.decode()
        assert 'value="gpt-5"' not in content
        assert 'value="claude-sonnet-5"' not in content

    def test_openai_provider_does_not_render_ollama_models_as_options(self, client, admin_user):
        engagement = _engagement_for(admin_user, provider="openai")
        _login(client, admin_user, engagement)

        response = client.get("/engagements/settings/llm/")
        content = response.content.decode()
        assert 'value="qwen2.5:7b"' not in content

    def test_all_provider_model_data_available_for_js_filtering(self, client, admin_user):
        """サーバー初期描画では絞り込むが、プロバイダ切替用に全件データはJSON化して埋め込まれていること。"""
        engagement = _engagement_for(admin_user, provider="ollama")
        _login(client, admin_user, engagement)

        response = client.get("/engagements/settings/llm/")
        content = response.content.decode()
        assert "gpt-5" in content
        assert "claude-sonnet-5" in content
        assert "qwen2.5:7b" in content

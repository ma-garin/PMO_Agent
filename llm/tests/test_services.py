from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth.models import User

from engagements.models import Engagement
from llm.models import LlmCallLog
from llm.providers.base import LlmError
from llm.services import run_completion


@pytest.fixture
def engagement(db) -> Engagement:
    owner = User.objects.create_user(username="pmo", password="x")
    return Engagement.objects.create(name="検証案件", owner=owner, llm_provider="claude")


@pytest.mark.django_db
class TestRunCompletion:
    def test_success_logs_call(self, engagement):
        fake_provider = MagicMock()
        fake_provider.complete.return_value = "応答テキスト"
        with patch("llm.services.get_provider", return_value=fake_provider) as mock_get:
            result = run_completion(engagement, "test_purpose", "prompt text")

        assert result == "応答テキスト"
        mock_get.assert_called_once_with("claude")
        log = LlmCallLog.objects.get()
        assert log.status == LlmCallLog.Status.SUCCESS
        assert log.provider == "claude"
        assert log.purpose == "test_purpose"
        assert log.response_chars == len("応答テキスト")

    def test_failure_logs_and_reraises(self, engagement):
        fake_provider = MagicMock()
        fake_provider.complete.side_effect = LlmError("接続失敗")
        with patch("llm.services.get_provider", return_value=fake_provider):
            with pytest.raises(LlmError):
                run_completion(engagement, "test_purpose", "prompt text")

        log = LlmCallLog.objects.get()
        assert log.status == LlmCallLog.Status.FAILED
        assert log.error_message == "接続失敗"

    def test_passes_engagement_api_key_to_provider(self, engagement):
        engagement.llm_api_key = "sk-engagement-key"
        engagement.save()

        fake_provider = MagicMock()
        fake_provider.complete.return_value = "ok"
        with patch("llm.services.get_provider", return_value=fake_provider):
            run_completion(engagement, "test_purpose", "prompt text")

        _, kwargs = fake_provider.complete.call_args
        assert kwargs["api_key"] == "sk-engagement-key"

    def test_passes_organization_and_project_only_for_openai(self, engagement):
        engagement.llm_provider = "openai"
        engagement.llm_api_key = "sk-engagement-key"
        engagement.llm_org_id = "org-123"
        engagement.llm_project_id = "proj-123"
        engagement.save()

        fake_provider = MagicMock()
        fake_provider.complete.return_value = "ok"
        with patch("llm.services.get_provider", return_value=fake_provider):
            run_completion(engagement, "test_purpose", "prompt text")

        _, kwargs = fake_provider.complete.call_args
        assert kwargs["organization"] == "org-123"
        assert kwargs["project"] == "proj-123"

    def test_claude_does_not_receive_organization_or_project_kwargs(self, engagement):
        engagement.llm_provider = "claude"
        engagement.llm_api_key = "sk-engagement-key"
        engagement.llm_org_id = "org-123"
        engagement.llm_project_id = "proj-123"
        engagement.save()

        fake_provider = MagicMock()
        fake_provider.complete.return_value = "ok"
        with patch("llm.services.get_provider", return_value=fake_provider):
            run_completion(engagement, "test_purpose", "prompt text")

        _, kwargs = fake_provider.complete.call_args
        assert "organization" not in kwargs
        assert "project" not in kwargs

    def test_no_api_key_falls_back_to_provider_defaults(self, engagement):
        """案件にAPIキー未設定なら kwargs に api_key を渡さず、providerが環境変数に
        フォールバックできるようにする(後方互換)。"""
        fake_provider = MagicMock()
        fake_provider.complete.return_value = "ok"
        with patch("llm.services.get_provider", return_value=fake_provider):
            run_completion(engagement, "test_purpose", "prompt text")

        _, kwargs = fake_provider.complete.call_args
        assert "api_key" not in kwargs

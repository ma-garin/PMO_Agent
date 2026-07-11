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

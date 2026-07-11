from datetime import datetime, timezone as dt_timezone

import pytest
from django.contrib.auth.models import User

from engagements.models import Engagement
from llm.models import LlmCallLog
from llm.services import usage_summary


@pytest.fixture
def owner(db) -> User:
    return User.objects.create_user(username="pmo", password="x")


def _log(engagement, provider, purpose, status, prompt_chars=10, response_chars=20, when=None):
    log = LlmCallLog.objects.create(
        engagement=engagement,
        provider=provider,
        purpose=purpose,
        prompt_chars=prompt_chars,
        response_chars=response_chars,
        status=status,
    )
    if when is not None:
        log.created_at = when
        log.save(update_fields=["created_at"])
    return log


@pytest.mark.django_db
class TestUsageSummary:
    def test_aggregates_call_count_and_chars_by_engagement_provider_purpose(self, owner):
        engagement = Engagement.objects.create(name="A案件", owner=owner, llm_provider="claude")
        _log(engagement, "claude", "copilot_chat", LlmCallLog.Status.SUCCESS, 10, 20)
        _log(engagement, "claude", "copilot_chat", LlmCallLog.Status.SUCCESS, 5, 15)

        rows = usage_summary(2026, 7)
        assert len(rows) == 1
        row = rows[0]
        assert row["call_count"] == 2
        assert row["total_chars"] == 50
        assert row["failure_count"] == 0
        assert row["failure_rate"] == 0.0

    def test_failure_rate_calculated_correctly(self, owner):
        engagement = Engagement.objects.create(name="A案件", owner=owner, llm_provider="claude")
        _log(engagement, "claude", "odc_suggest", LlmCallLog.Status.SUCCESS)
        _log(engagement, "claude", "odc_suggest", LlmCallLog.Status.FAILED)
        _log(engagement, "claude", "odc_suggest", LlmCallLog.Status.FAILED)

        rows = usage_summary(2026, 7)
        assert rows[0]["failure_count"] == 2
        assert rows[0]["failure_rate"] == 66.7

    def test_confidential_engagement_calling_cloud_provider_is_flagged(self, owner):
        engagement = Engagement.objects.create(name="機密案件", owner=owner, llm_provider="ollama")
        _log(engagement, "openai", "copilot_chat", LlmCallLog.Status.SUCCESS)

        rows = usage_summary(2026, 7)
        assert rows[0]["warning"] is True

    def test_confidential_engagement_calling_local_provider_is_not_flagged(self, owner):
        engagement = Engagement.objects.create(name="機密案件", owner=owner, llm_provider="ollama")
        _log(engagement, "ollama", "copilot_chat", LlmCallLog.Status.SUCCESS)

        rows = usage_summary(2026, 7)
        assert rows[0]["warning"] is False

    def test_calls_outside_month_are_excluded(self, owner):
        engagement = Engagement.objects.create(name="A案件", owner=owner, llm_provider="claude")
        _log(
            engagement,
            "claude",
            "copilot_chat",
            LlmCallLog.Status.SUCCESS,
            when=datetime(2026, 6, 15, tzinfo=dt_timezone.utc),
        )

        rows = usage_summary(2026, 7)
        assert rows == []

    def test_no_logs_returns_empty_list(self, owner):
        assert usage_summary(2026, 7) == []

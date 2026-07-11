from datetime import date
from unittest.mock import patch

import pytest
from django.contrib.auth.models import User

from copilot.models import ChatMessage, ChatThread
from copilot.services import UNREAD_THRESHOLD, create_auto_summary
from engagements.models import Engagement
from llm.providers.base import LlmError
from tickets.models import Notification, Ticket, TicketSource


@pytest.fixture
def engagement(db) -> Engagement:
    owner = User.objects.create_user(username="pmo", password="x")
    return Engagement.objects.create(name="検証案件", owner=owner)


@pytest.fixture
def ticket(engagement) -> Ticket:
    source = TicketSource.objects.create(
        engagement=engagement, kind="jira", name="s", base_url="https://x", project_key="P"
    )
    return Ticket.objects.create(source=source, external_id="1", summary="a")


def _make_unread(ticket, engagement, count: int) -> None:
    # Notificationはticket+kindでユニークなため、チケットごとに1件のみ作る
    source = ticket.source
    for i in range(count):
        t = Ticket.objects.create(source=source, external_id=f"gen-{i}", summary=f"チケット{i}")
        Notification.objects.create(
            engagement=engagement,
            ticket=t,
            kind=Notification.Kind.STAGNANT,
            message=f"通知{i}",
            is_read=False,
        )


@pytest.mark.django_db
class TestCreateAutoSummary:
    def test_below_threshold_creates_nothing(self, engagement, ticket):
        _make_unread(ticket, engagement, UNREAD_THRESHOLD - 1)
        result = create_auto_summary(engagement)
        assert result is None
        assert ChatThread.objects.count() == 0

    def test_at_threshold_creates_thread_with_assistant_message(self, engagement, ticket):
        _make_unread(ticket, engagement, UNREAD_THRESHOLD)
        with patch("copilot.services.run_completion", return_value="サマリー本文"):
            thread = create_auto_summary(engagement, today=date(2026, 7, 12))

        assert thread is not None
        assert thread.title == "(自動) 状況サマリー 2026-07-12"
        messages = ChatMessage.objects.filter(thread=thread)
        assert messages.count() == 1
        assert messages.first().role == ChatMessage.Role.ASSISTANT
        assert messages.first().content == "サマリー本文"

    def test_second_call_same_day_is_skipped(self, engagement, ticket):
        _make_unread(ticket, engagement, UNREAD_THRESHOLD)
        with patch("copilot.services.run_completion", return_value="1回目"):
            create_auto_summary(engagement, today=date(2026, 7, 12))
        with patch("copilot.services.run_completion", return_value="2回目") as mock_run:
            result = create_auto_summary(engagement, today=date(2026, 7, 12))

        mock_run.assert_not_called()
        assert result is None
        assert ChatThread.objects.count() == 1

    def test_next_day_creates_new_thread(self, engagement, ticket):
        _make_unread(ticket, engagement, UNREAD_THRESHOLD)
        with patch("copilot.services.run_completion", return_value="1回目"):
            create_auto_summary(engagement, today=date(2026, 7, 12))
        with patch("copilot.services.run_completion", return_value="2回目"):
            thread2 = create_auto_summary(engagement, today=date(2026, 7, 13))

        assert thread2 is not None
        assert ChatThread.objects.count() == 2

    def test_llm_failure_falls_back_to_template_message(self, engagement, ticket):
        _make_unread(ticket, engagement, UNREAD_THRESHOLD)
        with patch("copilot.services.run_completion", side_effect=LlmError("down")):
            thread = create_auto_summary(engagement, today=date(2026, 7, 12))

        message = ChatMessage.objects.get(thread=thread)
        assert f"{UNREAD_THRESHOLD}件" in message.content

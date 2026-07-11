from unittest.mock import patch

import pytest
from django.contrib.auth.models import User
from django.test import Client

from copilot.models import ChatMessage, ChatThread
from engagements.models import Engagement
from llm.providers.base import LlmError


@pytest.fixture
def user(db) -> User:
    return User.objects.create_user(username="pmo", password="x")


@pytest.fixture
def engagement(user) -> Engagement:
    e = Engagement.objects.create(name="検証案件", owner=user)
    e.members.add(user)
    return e


@pytest.fixture
def client_with_session(client: Client, user, engagement) -> Client:
    client.force_login(user)
    session = client.session
    session["current_engagement_id"] = engagement.pk
    session.save()
    return client


@pytest.mark.django_db
class TestSend:
    def test_send_saves_user_and_assistant_messages(self, client_with_session, engagement, user):
        thread = ChatThread.objects.create(engagement=engagement, created_by=user)
        with patch("copilot.views.run_completion", return_value="回答です"):
            client_with_session.post(
                f"/copilot/threads/{thread.pk}/send/", {"content": "今週のリスクは？"}
            )
        messages = list(thread.messages.all())
        assert len(messages) == 2
        assert messages[0].role == ChatMessage.Role.USER
        assert messages[1].role == ChatMessage.Role.ASSISTANT
        assert messages[1].content == "回答です"

    def test_thread_title_auto_named_from_first_question(self, client_with_session, engagement, user):
        thread = ChatThread.objects.create(engagement=engagement, created_by=user)
        with patch("copilot.views.run_completion", return_value="ok"):
            client_with_session.post(
                f"/copilot/threads/{thread.pk}/send/", {"content": "テスト戦略について教えて"}
            )
        thread.refresh_from_db()
        assert thread.title == "テスト戦略について教えて"

    def test_llm_error_does_not_save_assistant_message(self, client_with_session, engagement, user):
        thread = ChatThread.objects.create(engagement=engagement, created_by=user)
        with patch("copilot.views.run_completion", side_effect=LlmError("down")):
            client_with_session.post(
                f"/copilot/threads/{thread.pk}/send/", {"content": "質問"}
            )
        messages = list(thread.messages.all())
        assert len(messages) == 1
        assert messages[0].role == ChatMessage.Role.USER

    def test_other_engagements_thread_is_not_accessible(self, client_with_session, user):
        other_owner = User.objects.create_user(username="other", password="x")
        other_engagement = Engagement.objects.create(name="他案件", owner=other_owner)
        other_thread = ChatThread.objects.create(engagement=other_engagement, created_by=other_owner)

        response = client_with_session.get(f"/copilot/threads/{other_thread.pk}/")
        assert response.status_code == 404

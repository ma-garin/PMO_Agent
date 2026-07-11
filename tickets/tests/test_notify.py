from __future__ import annotations

from unittest.mock import patch

import pytest
import responses

from tickets.models import Notification, NotificationChannel, Ticket
from tickets.notify import deliver_notification


@pytest.fixture
def ticket(ticket_source):
    return Ticket.objects.create(source=ticket_source, external_id="PROJ-1", summary="停滞チケット")


@pytest.fixture
def notification(ticket, engagement):
    return Notification.objects.create(
        engagement=engagement,
        ticket=ticket,
        kind=Notification.Kind.STAGNANT,
        message="「停滞チケット」が5日以上更新されていません",
    )


@pytest.mark.django_db
class TestDeliverNotification:
    def test_inactive_channel_is_not_sent(self, engagement, notification):
        NotificationChannel.objects.create(
            engagement=engagement,
            kind=NotificationChannel.Kind.EMAIL,
            target="pmo@example.com",
            is_active=False,
        )
        with patch("tickets.notify.send_mail") as mock_send:
            delivered = deliver_notification(notification)

        mock_send.assert_not_called()
        assert delivered == 0

    def test_email_channel_calls_send_mail_with_message(self, engagement, notification):
        NotificationChannel.objects.create(
            engagement=engagement,
            kind=NotificationChannel.Kind.EMAIL,
            target="pmo@example.com",
        )
        with patch("tickets.notify.send_mail") as mock_send:
            delivered = deliver_notification(notification)

        mock_send.assert_called_once()
        _, kwargs = mock_send.call_args
        assert kwargs["message"] == notification.message
        assert kwargs["recipient_list"] == ["pmo@example.com"]
        assert delivered == 1

    @responses.activate
    def test_slack_channel_posts_message_text_payload(self, engagement, notification):
        webhook_url = "https://hooks.slack.com/services/T000/B000/xxx"
        NotificationChannel.objects.create(
            engagement=engagement,
            kind=NotificationChannel.Kind.SLACK_WEBHOOK,
            target=webhook_url,
        )
        responses.add(responses.POST, webhook_url, json={"ok": True}, status=200)

        delivered = deliver_notification(notification)

        assert delivered == 1
        assert len(responses.calls) == 1
        import json as _json

        sent_body = _json.loads(responses.calls[0].request.body)
        assert sent_body == {"text": notification.message}

    def test_other_engagement_channel_not_used(self, notification):
        from engagements.models import Engagement

        from django.contrib.auth.models import User

        other_owner = User.objects.create_user(username="other", password="x")
        other_engagement = Engagement.objects.create(name="別案件", owner=other_owner)
        NotificationChannel.objects.create(
            engagement=other_engagement,
            kind=NotificationChannel.Kind.EMAIL,
            target="other@example.com",
        )
        with patch("tickets.notify.send_mail") as mock_send:
            delivered = deliver_notification(notification)

        mock_send.assert_not_called()
        assert delivered == 0

    def test_failure_in_one_channel_does_not_block_others(self, engagement, notification):
        NotificationChannel.objects.create(
            engagement=engagement, kind=NotificationChannel.Kind.EMAIL, target="a@example.com"
        )
        NotificationChannel.objects.create(
            engagement=engagement, kind=NotificationChannel.Kind.EMAIL, target="b@example.com"
        )
        with patch("tickets.notify.send_mail", side_effect=[Exception("smtp down"), None]):
            delivered = deliver_notification(notification)

        assert delivered == 1

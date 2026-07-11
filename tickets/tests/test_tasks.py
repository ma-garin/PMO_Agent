from __future__ import annotations

from unittest.mock import patch

import pytest

from tickets.models import Notification, Ticket
from tickets.tasks import deliver_notification_task, sync_and_detect_engagement


@pytest.fixture
def ticket(ticket_source):
    return Ticket.objects.create(source=ticket_source, external_id="PROJ-1", summary="停滞チケット")


@pytest.mark.django_db
class TestSyncAndDetectEngagement:
    def test_defers_delivery_task_for_each_created_notification(self, engagement, ticket):
        notification = Notification(
            engagement=engagement, ticket=ticket, kind=Notification.Kind.STAGNANT, message="停滞"
        )
        notification.pk = 1

        with (
            patch("tickets.tasks.sync_engagement"),
            patch("tickets.tasks.detect_stagnant_tickets", return_value=[notification]),
            patch.object(deliver_notification_task, "defer") as mock_defer,
        ):
            sync_and_detect_engagement(engagement_id=engagement.pk)

        mock_defer.assert_called_once_with(notification_id=1)

    def test_no_notifications_means_no_defer_calls(self, engagement):
        with (
            patch("tickets.tasks.sync_engagement"),
            patch("tickets.tasks.detect_stagnant_tickets", return_value=[]),
            patch.object(deliver_notification_task, "defer") as mock_defer,
        ):
            sync_and_detect_engagement(engagement_id=engagement.pk)

        mock_defer.assert_not_called()

    def test_calls_create_auto_summary_after_detection(self, engagement):
        with (
            patch("tickets.tasks.sync_engagement"),
            patch("tickets.tasks.detect_stagnant_tickets", return_value=[]),
            patch("copilot.services.create_auto_summary") as mock_auto_summary,
        ):
            sync_and_detect_engagement(engagement_id=engagement.pk)

        mock_auto_summary.assert_called_once_with(engagement)


@pytest.mark.django_db
class TestDeliverNotificationTask:
    def test_missing_notification_is_skipped_without_error(self):
        with patch("tickets.notify.deliver_notification") as mock_deliver:
            deliver_notification_task(notification_id=999999)
        mock_deliver.assert_not_called()

    def test_existing_notification_is_delivered(self, engagement, ticket):
        notification = Notification.objects.create(
            engagement=engagement, ticket=ticket, kind=Notification.Kind.STAGNANT, message="停滞"
        )
        with patch("tickets.tasks.deliver_notification") as mock_deliver:
            deliver_notification_task(notification_id=notification.pk)
        mock_deliver.assert_called_once_with(notification)

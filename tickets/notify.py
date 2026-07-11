"""通知チャネル(メール/Slack)への配信。文面はテンプレート固定でLLM生成文は送らない。"""

from __future__ import annotations

import logging

import requests
from django.conf import settings
from django.core.mail import send_mail

from .models import Notification, NotificationChannel

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT_SECONDS = 10


def _send_email(channel: NotificationChannel, notification: Notification) -> None:
    send_mail(
        subject=f"[PMO Agent] {notification.get_kind_display()}通知",
        message=notification.message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[channel.target],
        fail_silently=False,
    )


def _send_slack(channel: NotificationChannel, notification: Notification) -> None:
    response = requests.post(
        channel.target,
        json={"text": notification.message},
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()


def deliver_notification(notification: Notification) -> int:
    """有効な通知チャネル全てに配信する。成功件数を返す。"""
    channels = NotificationChannel.objects.filter(
        engagement=notification.engagement, is_active=True
    )
    delivered = 0
    for channel in channels:
        try:
            if channel.kind == NotificationChannel.Kind.EMAIL:
                _send_email(channel, notification)
            elif channel.kind == NotificationChannel.Kind.SLACK_WEBHOOK:
                _send_slack(channel, notification)
            else:
                continue
            delivered += 1
        except Exception:
            logger.exception("通知配信に失敗しました: channel_id=%s", channel.pk)
    return delivered

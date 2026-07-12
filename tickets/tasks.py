"""Procrastinateタスク定義。

`tickets/views.py` の「今すぐ同期」ボタン(同期呼び出し)とは別に、
定期実行・非同期実行のための経路として `sync_engagement` / `detect_stagnant_tickets`
をラップする。ここで定義したタスクは views.py の同期処理を置き換えない。
"""

from __future__ import annotations

import logging

from procrastinate.contrib.django import app

from engagements.models import Engagement

from .notify import deliver_notification
from .services import detect_stagnant_tickets, sync_engagement

logger = logging.getLogger(__name__)


@app.task(name="tickets.sync_engagement_sources")
def sync_engagement_sources(engagement_id: int) -> None:
    """指定した案件のアクティブなTicketSourceを同期する。"""
    engagement = Engagement.objects.filter(pk=engagement_id).first()
    if engagement is None:
        # defer後に案件が削除された場合はスキップする(ジョブを失敗させない)
        logger.warning("案件が見つからないため同期をスキップしました: engagement_id=%s", engagement_id)
        return
    sync_engagement(engagement)


@app.task(name="tickets.deliver_notification_task")
def deliver_notification_task(notification_id: int) -> None:
    """通知チャネル(メール/Slack)へ配信する。"""
    from .models import Notification

    notification = Notification.objects.filter(pk=notification_id).select_related(
        "engagement"
    ).first()
    if notification is None:
        logger.warning("通知が見つからないため配信をスキップしました: notification_id=%s", notification_id)
        return
    deliver_notification(notification)


@app.task(name="tickets.sync_and_detect_engagement")
def sync_and_detect_engagement(engagement_id: int) -> None:
    """指定した案件を同期し、続けて停滞チケットを検知・通知配信する。"""
    engagement = Engagement.objects.filter(pk=engagement_id).first()
    if engagement is None:
        logger.warning("案件が見つからないため同期・検知をスキップしました: engagement_id=%s", engagement_id)
        return
    sync_engagement(engagement)
    created_notifications = detect_stagnant_tickets(engagement)
    for notification in created_notifications:
        deliver_notification_task.defer(notification_id=notification.pk)

    try:
        from copilot.services import create_auto_summary
    except ImportError:
        pass
    else:
        create_auto_summary(engagement)

    try:
        from autopilot.models import AgentSettings
        from autopilot.tasks import event_patrol
    except ImportError:
        pass
    else:
        if AgentSettings.objects.filter(engagement=engagement, enabled=True).exists():
            event_patrol.defer(engagement_id=engagement.pk)


@app.periodic(cron="0 * * * *")  # 毎時0分。外部API負荷とのバランスから1時間間隔とする
@app.task(name="tickets.sync_and_detect_all_engagements")
def sync_and_detect_all_engagements(timestamp: int) -> None:
    """全案件を対象に同期+停滞検知をdeferする(定期実行の起点)。

    Procrastinateワーカーが起動している間、ワーカー自身がこの周期タスクを
    スケジュールに従ってdeferする(cron等の外部トリガーは不要)。
    """
    engagement_ids = Engagement.objects.values_list("id", flat=True)
    for engagement_id in engagement_ids:
        sync_and_detect_engagement.defer(engagement_id=engagement_id)

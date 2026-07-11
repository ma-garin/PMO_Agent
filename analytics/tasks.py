"""Procrastinateタスク定義(週次サマリー自動生成)。"""

from __future__ import annotations

import logging

from procrastinate.contrib.django import app

from engagements.models import Engagement

from .services import generate_weekly_digest

logger = logging.getLogger(__name__)


@app.periodic(cron="0 9 * * 1")  # 毎週月曜9:00。先週分のサマリーを生成する
@app.task(name="analytics.generate_weekly_digests")
def generate_weekly_digests(timestamp: int) -> None:
    engagement_ids = Engagement.objects.filter(
        status=Engagement.Status.ACTIVE
    ).values_list("id", flat=True)
    for engagement_id in engagement_ids:
        engagement = Engagement.objects.filter(pk=engagement_id).first()
        if engagement is None:
            continue
        try:
            generate_weekly_digest(engagement)
        except Exception:
            logger.exception("週次サマリー生成に失敗しました: engagement_id=%s", engagement_id)

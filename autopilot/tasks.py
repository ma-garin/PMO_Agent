"""Procrastinateタスク定義(自律運転の巡回)。"""

from __future__ import annotations

import logging

from procrastinate.contrib.django import app

from engagements.models import Engagement

from .models import AgentSettings
from .services import run_patrol

logger = logging.getLogger(__name__)


@app.periodic(cron="30 8 * * *")  # 毎日8:30に定期巡回
@app.task(name="autopilot.daily_patrol")
def daily_patrol(timestamp: int) -> None:
    engagement_ids = AgentSettings.objects.filter(enabled=True).values_list(
        "engagement_id", flat=True
    )
    for engagement_id in engagement_ids:
        engagement = Engagement.objects.filter(pk=engagement_id).first()
        if engagement is None:
            continue
        run_patrol(engagement, trigger="scheduled")


@app.task(name="autopilot.event_patrol")
def event_patrol(engagement_id: int) -> None:
    engagement = Engagement.objects.filter(pk=engagement_id).first()
    if engagement is None:
        logger.warning("案件が見つからないため巡回をスキップしました: engagement_id=%s", engagement_id)
        return
    run_patrol(engagement, trigger="event")

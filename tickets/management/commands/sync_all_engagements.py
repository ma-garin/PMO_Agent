"""全案件の同期+停滞検知をProcrastinateジョブとしてdeferする管理コマンド。

Procrastinateの周期タスク(`tickets.tasks.sync_and_detect_all_engagements`)が
定期実行の主経路だが、ワーカー未起動時の動作確認や、将来launchd等の外部cronから
明示的に起動したい場合のためにコマンドとしても用意しておく。
"""

from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand

from engagements.models import Engagement
from tickets.tasks import sync_and_detect_engagement


class Command(BaseCommand):
    help = "全案件を対象に、チケット同期と停滞検知をProcrastinateジョブとしてdeferする"

    def handle(self, *args: Any, **options: Any) -> None:
        engagement_ids = list(Engagement.objects.values_list("id", flat=True))
        for engagement_id in engagement_ids:
            sync_and_detect_engagement.defer(engagement_id=engagement_id)

        self.stdout.write(
            self.style.SUCCESS(
                f"{len(engagement_ids)}件の案件について同期・停滞検知ジョブを登録しました。"
            )
        )

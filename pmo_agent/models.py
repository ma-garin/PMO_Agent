from django.conf import settings
from django.db import models


class PmoTaskStore(models.Model):
    """PMO Agent MVPのWBSタスクを案件単位で保持するJSONストア。

    クライアント(mvp.html)は常にタスク配列の全量を保存する設計のため、
    行分解せず配列ごと保持する。storeHashはクライアント算出のSHA-256で、
    楽観ロック(baseStoreHash照合)にのみ使うopaque値として扱う。
    """

    engagement = models.OneToOneField(
        "engagements.Engagement", on_delete=models.CASCADE, related_name="pmo_task_store"
    )
    tasks = models.JSONField("タスク一覧", default=list, blank=True)
    saved_at = models.CharField("保存日時(ISO)", max_length=40, blank=True)
    store_hash = models.CharField("ストアハッシュ", max_length=64, blank=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="pmo_task_stores",
    )
    updated_at = models.DateTimeField("更新日時", auto_now=True)

    def __str__(self) -> str:
        return f"{self.engagement.name} ({len(self.tasks)}件)"

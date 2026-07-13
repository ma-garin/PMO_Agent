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


class PmoJsonStore(models.Model):
    """報告/KPI/AI提案などHITL成果物を案件×種別で保持する汎用JSONストア。

    クライアントは各ストアのペイロード全量を保存する。保存のたびにAuditLogへ
    記録するため、payload内の表示用ログが上書きされても監査証跡はDBに残る。
    """

    class Kind(models.TextChoices):
        REPORT = "report", "報告生成・承認"
        KPI = "kpi", "KPI・効果測定"
        PROPOSAL = "proposal", "AI介入提案"

    engagement = models.ForeignKey(
        "engagements.Engagement", on_delete=models.CASCADE, related_name="pmo_json_stores"
    )
    kind = models.CharField("種別", max_length=20, choices=Kind.choices)
    payload = models.JSONField("ペイロード", default=dict, blank=True)
    saved_at = models.CharField("保存日時(ISO)", max_length=40, blank=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="pmo_json_stores",
    )
    updated_at = models.DateTimeField("更新日時", auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["engagement", "kind"], name="uniq_pmo_json_store_engagement_kind"
            )
        ]

    def __str__(self) -> str:
        return f"{self.engagement.name} / {self.get_kind_display()}"


class UserAiQuota(models.Model):
    """ユーザーごとの月間トークン上限(0=無制限)。LLMコスト管理に使う。"""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="ai_quota"
    )
    monthly_token_limit = models.PositiveIntegerField("月間トークン上限(0=無制限)", default=0)
    updated_at = models.DateTimeField("更新日時", auto_now=True)

    def __str__(self) -> str:
        return f"{self.user.username}: {self.monthly_token_limit}"

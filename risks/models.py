from django.conf import settings
from django.db import models

HIGH_SCORE_THRESHOLD = 15
MEDIUM_SCORE_THRESHOLD = 8


class RiskItem(models.Model):
    class Status(models.TextChoices):
        IDENTIFIED = "identified", "識別"
        MONITORING = "monitoring", "監視中"
        MATERIALIZED = "materialized", "顕在化"
        CLOSED = "closed", "クローズ"

    engagement = models.ForeignKey(
        "engagements.Engagement", on_delete=models.CASCADE, related_name="risks"
    )
    title = models.CharField("リスク", max_length=200)
    description = models.TextField("内容", blank=True)
    probability = models.PositiveSmallIntegerField("発生確率(1-5)", default=3)
    impact = models.PositiveSmallIntegerField("影響度(1-5)", default=3)
    measurement = models.CharField("測定方法", max_length=300, blank=True)
    countermeasure = models.TextField("顕在化時の対策", blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.IDENTIFIED)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    due_date = models.DateField("対応期限", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["status", "-updated_at"]

    def __str__(self) -> str:
        return self.title

    @property
    def score(self) -> int:
        return self.probability * self.impact

    @property
    def severity(self) -> str:
        if self.score >= HIGH_SCORE_THRESHOLD:
            return "high"
        if self.score >= MEDIUM_SCORE_THRESHOLD:
            return "medium"
        return "low"


class ImprovementAction(models.Model):
    class Status(models.TextChoices):
        PLANNED = "planned", "計画"
        IN_PROGRESS = "in_progress", "実行中"
        DONE = "done", "完了"
        CANCELLED = "cancelled", "中止"

    engagement = models.ForeignKey(
        "engagements.Engagement", on_delete=models.CASCADE, related_name="improvement_actions"
    )
    title = models.CharField("アクション", max_length=200)
    background = models.TextField("背景・根拠", blank=True)
    origin_risk = models.ForeignKey(
        RiskItem, null=True, blank=True, on_delete=models.SET_NULL, related_name="actions"
    )
    origin_note = models.CharField("起点(自由記述)", max_length=200, blank=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    due_date = models.DateField("期限", null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PLANNED)
    effect_note = models.TextField("効果確認メモ", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["status", "due_date"]

    def __str__(self) -> str:
        return self.title


class GeneralNotification(models.Model):
    """ticketsに紐づかない通知(期限超過リスク・改善アクション等)。

    tickets.Notificationはticket必須のためリスク/アクション向けに新設(Phase 7仕様)。
    """

    class Kind(models.TextChoices):
        RISK_OVERDUE = "risk_overdue", "リスク対応期限超過"
        ACTION_OVERDUE = "action_overdue", "改善アクション期限超過"
        AGENT_PROPOSAL = "agent_proposal", "エージェント提案"

    engagement = models.ForeignKey(
        "engagements.Engagement", on_delete=models.CASCADE, related_name="general_notifications"
    )
    kind = models.CharField(max_length=30, choices=Kind.choices)
    message = models.CharField("内容", max_length=300)
    is_read = models.BooleanField("既読", default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["engagement", "kind", "message"], name="unique_general_notification"
            )
        ]

    def __str__(self) -> str:
        return self.message

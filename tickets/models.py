from django.db import models

from config.crypto import decrypt, encrypt
from engagements.models import Engagement


class TicketSource(models.Model):
    class Kind(models.TextChoices):
        JIRA = "jira", "JIRA"
        REDMINE = "redmine", "Redmine"

    engagement = models.ForeignKey(
        Engagement, related_name="ticket_sources", on_delete=models.CASCADE
    )
    kind = models.CharField("種別", max_length=20, choices=Kind.choices)
    name = models.CharField("表示名", max_length=100)
    base_url = models.URLField("接続先URL")
    project_key = models.CharField("プロジェクトキー", max_length=100)
    username = models.CharField("ユーザー名/メール", max_length=200, blank=True)
    _api_token_encrypted = models.TextField(
        "APIトークン(暗号化)", blank=True, db_column="api_token_encrypted"
    )
    is_active = models.BooleanField("同期を有効にする", default=True)
    last_synced_at = models.DateTimeField("最終同期日時", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.get_kind_display()}: {self.name}"

    @property
    def api_token(self) -> str:
        return decrypt(self._api_token_encrypted)

    @api_token.setter
    def api_token(self, value: str) -> None:
        self._api_token_encrypted = encrypt(value)


class Ticket(models.Model):
    source = models.ForeignKey(
        TicketSource, related_name="tickets", on_delete=models.CASCADE
    )
    external_id = models.CharField("元チケットID", max_length=50)
    external_url = models.URLField("元チケットURL", blank=True)
    summary = models.CharField("概要", max_length=500)
    description = models.TextField("本文", blank=True)
    status = models.CharField("状態(元システム)", max_length=100, blank=True)
    is_done = models.BooleanField("完了済み", default=False)
    priority = models.CharField("優先度(元システム)", max_length=100, blank=True)
    ticket_type = models.CharField("種別(元システム)", max_length=100, blank=True)
    assignee_name = models.CharField("担当者", max_length=200, blank=True)
    reporter_name = models.CharField("報告者", max_length=200, blank=True)
    due_date = models.DateField("期限", null=True, blank=True)
    source_created_at = models.DateTimeField("元システムでの作成日時", null=True, blank=True)
    source_updated_at = models.DateTimeField("元システムでの更新日時", null=True, blank=True)
    closed_at = models.DateTimeField("クローズ日時", null=True, blank=True)
    raw_payload = models.JSONField("元データ", default=dict, blank=True)
    synced_at = models.DateTimeField("取込日時", auto_now=True)

    class Meta:
        ordering = ["-source_updated_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["source", "external_id"], name="unique_ticket_per_source"
            )
        ]

    def __str__(self) -> str:
        return f"{self.external_id}: {self.summary}"

    @property
    def engagement(self) -> Engagement:
        return self.source.engagement


class TicketStatusTransition(models.Model):
    """チケットのステータス遷移履歴(読み取り専用取込)。再オープン率算出に使う。"""

    ticket = models.ForeignKey(
        Ticket, related_name="status_transitions", on_delete=models.CASCADE
    )
    from_status = models.CharField("変更前ステータス", max_length=100, blank=True)
    to_status = models.CharField("変更後ステータス", max_length=100)
    occurred_at = models.DateTimeField("発生日時")

    class Meta:
        ordering = ["occurred_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["ticket", "occurred_at", "to_status"], name="unique_status_transition"
            )
        ]

    def __str__(self) -> str:
        return f"{self.ticket}: {self.from_status} → {self.to_status}"


class NotificationChannel(models.Model):
    """通知の外部連携先(メール/Slack)。文面はテンプレート固定、LLM生成文は送らない。"""

    class Kind(models.TextChoices):
        EMAIL = "email", "メール"
        SLACK_WEBHOOK = "slack_webhook", "Slack Incoming Webhook"

    engagement = models.ForeignKey(
        Engagement, related_name="notification_channels", on_delete=models.CASCADE
    )
    kind = models.CharField("種別", max_length=20, choices=Kind.choices)
    target = models.CharField("宛先(メールアドレス/Webhook URL)", max_length=500)
    is_active = models.BooleanField("有効", default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.engagement.name}: {self.get_kind_display()} ({self.target})"


class SyncRun(models.Model):
    class Status(models.TextChoices):
        RUNNING = "running", "実行中"
        SUCCESS = "success", "成功"
        FAILED = "failed", "失敗"

    source = models.ForeignKey(
        TicketSource, related_name="sync_runs", on_delete=models.CASCADE
    )
    status = models.CharField(
        "状態", max_length=20, choices=Status.choices, default=Status.RUNNING
    )
    tickets_synced = models.PositiveIntegerField("同期件数", default=0)
    error_message = models.TextField("エラー内容", blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-started_at"]

    def __str__(self) -> str:
        return f"{self.source} @ {self.started_at:%Y-%m-%d %H:%M}"


class StagnationRule(models.Model):
    engagement = models.OneToOneField(
        Engagement, related_name="stagnation_rule", on_delete=models.CASCADE
    )
    stale_after_days = models.PositiveSmallIntegerField("更新なし停滞判定(日)", default=5)
    notify_on_overdue = models.BooleanField("期限超過も検知する", default=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"{self.engagement.name} の停滞条件"


class Notification(models.Model):
    class Kind(models.TextChoices):
        STAGNANT = "stagnant", "停滞"
        OVERDUE = "overdue", "期限超過"

    engagement = models.ForeignKey(
        Engagement, related_name="notifications", on_delete=models.CASCADE
    )
    ticket = models.ForeignKey(
        Ticket, related_name="notifications", on_delete=models.CASCADE
    )
    kind = models.CharField("種別", max_length=20, choices=Kind.choices)
    message = models.CharField("内容", max_length=300)
    is_read = models.BooleanField("既読", default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["ticket", "kind"], name="unique_notification_per_ticket_kind"
            )
        ]

    def __str__(self) -> str:
        return self.message

from django.conf import settings
from django.db import models


class LlmCallLog(models.Model):
    """全LLM呼び出しの監査ログ(ADR-0002)。プロンプト原文は保存しない(機密)。"""

    class Status(models.TextChoices):
        SUCCESS = "success", "成功"
        FAILED = "failed", "失敗"

    engagement = models.ForeignKey(
        "engagements.Engagement", on_delete=models.CASCADE, related_name="llm_call_logs"
    )
    provider = models.CharField("プロバイダ", max_length=20)
    purpose = models.CharField("用途", max_length=50)
    prompt_chars = models.PositiveIntegerField("プロンプト文字数", default=0)
    response_chars = models.PositiveIntegerField("応答文字数", default=0)
    status = models.CharField(max_length=20, choices=Status.choices)
    error_message = models.TextField(blank=True)
    duration_ms = models.PositiveIntegerField(default=0)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.provider}/{self.purpose} ({self.status})"

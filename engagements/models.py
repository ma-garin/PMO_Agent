from django.conf import settings
from django.db import models


class Engagement(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "進行中"
        ON_HOLD = "on_hold", "保留中"
        COMPLETED = "completed", "完了"

    class LlmProvider(models.TextChoices):
        OPENAI = "openai", "OpenAI API"
        CLAUDE = "claude", "Claude API"
        OLLAMA = "ollama", "ローカルLLM (Ollama)"

    name = models.CharField("案件名", max_length=200)
    description = models.CharField("概要", max_length=300, blank=True)
    status = models.CharField(
        "ステータス", max_length=20, choices=Status.choices, default=Status.ACTIVE
    )
    progress = models.PositiveSmallIntegerField("進捗率(%)", default=0)
    members = models.ManyToManyField(
        settings.AUTH_USER_MODEL, related_name="engagements", blank=True
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="owned_engagements",
        on_delete=models.CASCADE,
    )
    llm_provider = models.CharField(
        "既定LLMプロバイダ",
        max_length=20,
        choices=LlmProvider.choices,
        default=LlmProvider.OLLAMA,
    )
    updated_at = models.DateTimeField("更新日時", auto_now=True)
    created_at = models.DateTimeField("作成日時", auto_now_add=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self) -> str:
        return self.name

    @property
    def member_count(self) -> int:
        return self.members.count()


class ActivityLog(models.Model):
    engagement = models.ForeignKey(
        Engagement, related_name="activities", on_delete=models.CASCADE
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+"
    )
    message = models.CharField("内容", max_length=300)
    created_at = models.DateTimeField("発生日時", auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.message

from django.conf import settings
from django.db import models


class Report(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "ドラフト"
        APPROVED = "approved", "承認済み"

    engagement = models.ForeignKey(
        "engagements.Engagement", on_delete=models.CASCADE, related_name="reports"
    )
    title = models.CharField("タイトル", max_length=200)
    period_start = models.DateField("対象期間(自)")
    period_end = models.DateField("対象期間(至)")
    body = models.TextField("本文", blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.title


class ReportTemplate(models.Model):
    """AIドラフト生成時のシステムプロンプト(章立て)を管理者が差し替えられるようにするテンプレート。"""

    name = models.CharField("テンプレート名", max_length=200)
    system_prompt = models.TextField("システムプロンプト")
    is_default = models.BooleanField("既定テンプレート", default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_default", "name"]

    def __str__(self) -> str:
        return self.name

from django.conf import settings
from django.db import models


class TestPlan(models.Model):
    class Kind(models.TextChoices):
        MASTER = "master", "マスターテスト計画"
        LEVEL = "level", "レベルテスト計画"

    class Status(models.TextChoices):
        DRAFT = "draft", "ドラフト"
        APPROVED = "approved", "承認済み"

    engagement = models.ForeignKey(
        "engagements.Engagement", on_delete=models.CASCADE, related_name="test_plans"
    )
    kind = models.CharField(max_length=10, choices=Kind.choices)
    title = models.CharField("タイトル", max_length=200)
    test_level = models.CharField("対象テストレベル", max_length=50, blank=True)
    body = models.TextField("本文", blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.title


class TestProgressEntry(models.Model):
    engagement = models.ForeignKey(
        "engagements.Engagement", on_delete=models.CASCADE, related_name="test_progress"
    )
    test_level = models.CharField("テストレベル", max_length=50)
    date = models.DateField("日付")
    planned_cases = models.PositiveIntegerField("計画累計", default=0)
    executed_cases = models.PositiveIntegerField("実行累計", default=0)
    passed_cases = models.PositiveIntegerField("合格累計", default=0)
    note = models.CharField("メモ", max_length=200, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["engagement", "test_level", "date"], name="unique_progress_per_day"
            )
        ]
        ordering = ["test_level", "date"]

    def __str__(self) -> str:
        return f"{self.test_level} {self.date}"


class QualityGate(models.Model):
    class Verdict(models.TextChoices):
        PENDING = "pending", "判定前"
        PASSED = "passed", "合格"
        FAILED = "failed", "不合格"

    engagement = models.ForeignKey(
        "engagements.Engagement", on_delete=models.CASCADE, related_name="quality_gates"
    )
    name = models.CharField("ゲート名", max_length=100)
    criteria = models.JSONField("判定条件", default=dict)
    verdict = models.CharField(max_length=10, choices=Verdict.choices, default=Verdict.PENDING)
    judged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    judged_at = models.DateTimeField(null=True, blank=True)
    note = models.TextField("判定コメント", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.name

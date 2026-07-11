from django.conf import settings
from django.db import models


class TpiKeyArea(models.Model):
    """キーエリアのマスター。内容はユーザーが投入する(書籍原文は同梱しない)。"""

    name = models.CharField("キーエリア名", max_length=100, unique=True)
    description = models.CharField("説明", max_length=300, blank=True)
    order = models.PositiveSmallIntegerField("表示順", default=0)
    is_active = models.BooleanField("有効", default=True)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self) -> str:
        return self.name


class MaturityLevel(models.TextChoices):
    CONTROLLED = "controlled", "コントロールド"
    EFFICIENT = "efficient", "エフィシェント"
    OPTIMIZING = "optimizing", "オプティマイジング"


LEVEL_ORDER = ["controlled", "efficient", "optimizing"]


class TpiCheckpoint(models.Model):
    key_area = models.ForeignKey(TpiKeyArea, on_delete=models.CASCADE, related_name="checkpoints")
    level = models.CharField("成熟度レベル", max_length=20, choices=MaturityLevel.choices)
    text = models.CharField("チェックポイント", max_length=500)
    order = models.PositiveSmallIntegerField("表示順", default=0)

    class Meta:
        ordering = ["key_area", "level", "order", "id"]

    def __str__(self) -> str:
        return self.text[:50]


class TpiAssessment(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "実施中"
        FINAL = "final", "確定"

    engagement = models.ForeignKey(
        "engagements.Engagement", on_delete=models.CASCADE, related_name="tpi_assessments"
    )
    title = models.CharField("タイトル", max_length=200)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    suggestion = models.TextField("改善提言", blank=True)
    assessed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.title


class TpiAnswer(models.Model):
    class Result(models.TextChoices):
        MET = "met", "充足"
        NOT_MET = "not_met", "未充足"
        NA = "na", "対象外"

    assessment = models.ForeignKey(TpiAssessment, on_delete=models.CASCADE, related_name="answers")
    checkpoint = models.ForeignKey(TpiCheckpoint, on_delete=models.CASCADE, related_name="+")
    result = models.CharField(max_length=10, choices=Result.choices, default=Result.NOT_MET)
    note = models.CharField("メモ", max_length=300, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["assessment", "checkpoint"], name="unique_answer_per_checkpoint"
            )
        ]

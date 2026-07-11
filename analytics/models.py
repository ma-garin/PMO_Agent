from django.conf import settings
from django.db import models

from tickets.models import Ticket


class OdcClassification(models.Model):
    """欠陥チケットへのODC分類(固定4軸)。

    出所(source)と確定状態(status)を必ず持ち、確定分のみ分析に使う
    (docs/DESIGN.md 3.2)。Phase 2は手動分類のみ、LLM推定はPhase 3で追加。
    """

    class DefectType(models.TextChoices):
        FUNCTION = "function", "機能"
        ASSIGNMENT = "assignment", "割付・初期化"
        CHECKING = "checking", "チェック"
        ALGORITHM = "algorithm", "アルゴリズム"
        TIMING = "timing", "タイミング・直列化"
        INTERFACE = "interface", "インターフェース"
        RELATIONSHIP = "relationship", "関連"
        DOCUMENTATION = "documentation", "ドキュメント"

    class Trigger(models.TextChoices):
        DESIGN_CONFORMANCE = "design_conformance", "設計適合性"
        COVERAGE = "coverage", "カバレッジ"
        VARIATION = "variation", "バリエーション"
        SEQUENCING = "sequencing", "シーケンス"
        INTERACTION = "interaction", "相互作用"
        WORKLOAD = "workload", "負荷・ストレス"
        REGRESSION = "regression", "回帰"
        CONFIGURATION = "configuration", "設定・環境"

    class Activity(models.TextChoices):
        REQ_REVIEW = "req_review", "要件レビュー"
        DESIGN_REVIEW = "design_review", "設計レビュー"
        CODE_REVIEW = "code_review", "コードレビュー"
        UNIT_TEST = "unit_test", "単体テスト"
        INTEGRATION_TEST = "integration_test", "結合テスト"
        SYSTEM_TEST = "system_test", "システムテスト"
        ACCEPTANCE_TEST = "acceptance_test", "受入テスト"
        PRODUCTION = "production", "本番・運用"

    class Impact(models.TextChoices):
        CRITICAL = "critical", "致命的"
        MAJOR = "major", "重大"
        MODERATE = "moderate", "中程度"
        MINOR = "minor", "軽微"

    class Source(models.TextChoices):
        FIELD = "field", "チケットフィールド由来"
        LLM = "llm", "LLM推定"
        MANUAL = "manual", "手動"

    class Status(models.TextChoices):
        PENDING = "pending", "レビュー待ち"
        CONFIRMED = "confirmed", "確定済み"

    ticket = models.OneToOneField(
        Ticket, related_name="odc_classification", on_delete=models.CASCADE
    )
    defect_type = models.CharField(
        "欠陥タイプ", max_length=30, choices=DefectType.choices, blank=True
    )
    trigger = models.CharField(
        "トリガー", max_length=30, choices=Trigger.choices, blank=True
    )
    activity = models.CharField(
        "検出アクティビティ", max_length=30, choices=Activity.choices, blank=True
    )
    impact = models.CharField(
        "影響度", max_length=30, choices=Impact.choices, blank=True
    )
    source = models.CharField(
        "出所", max_length=20, choices=Source.choices, default=Source.MANUAL
    )
    status = models.CharField(
        "確定状態", max_length=20, choices=Status.choices, default=Status.PENDING
    )
    classified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"ODC: {self.ticket}"


class WeeklyDigest(models.Model):
    """週次サマリー(自動生成)。週の開始日(月曜)ごとに1件、冪等に上書きされる。"""

    engagement = models.ForeignKey(
        "engagements.Engagement", related_name="weekly_digests", on_delete=models.CASCADE
    )
    week_start = models.DateField("週の開始日(月曜)")
    body = models.TextField("要約本文")
    metrics = models.JSONField("集計指標", default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-week_start"]
        constraints = [
            models.UniqueConstraint(
                fields=["engagement", "week_start"], name="unique_digest_per_week"
            )
        ]

    def __str__(self) -> str:
        return f"{self.engagement.name} {self.week_start} の週次サマリー"

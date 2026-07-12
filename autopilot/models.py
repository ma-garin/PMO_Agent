from django.conf import settings
from django.db import models


class AgentSettings(models.Model):
    """案件ごとの自律運転設定。レコードが無い案件は運転OFF扱い。"""

    engagement = models.OneToOneField(
        "engagements.Engagement", on_delete=models.CASCADE, related_name="agent_settings"
    )
    enabled = models.BooleanField("自律運転を有効にする", default=False)
    stagnant_spike_threshold = models.PositiveSmallIntegerField(
        "停滞急増の閾値(24h件数)", default=5
    )
    defect_spike_threshold = models.PositiveSmallIntegerField(
        "欠陥急増の閾値(24h件数)", default=5
    )
    overdue_threshold = models.PositiveSmallIntegerField("期限超過の閾値(累計件数)", default=3)
    schedule_slip_threshold = models.PositiveSmallIntegerField(
        "WBS遅延の閾値(件数)", default=1
    )
    max_llm_calls_per_day = models.PositiveSmallIntegerField("LLM呼び出し上限(日)", default=20)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"{self.engagement.name} の自律運転設定"


class AgentRun(models.Model):
    """巡回の実行記録。"""

    class Trigger(models.TextChoices):
        SCHEDULED = "scheduled", "定期"
        EVENT = "event", "同期後イベント"
        MANUAL = "manual", "手動"

    class Status(models.TextChoices):
        RUNNING = "running", "実行中"
        SUCCESS = "success", "成功"
        FAILED = "failed", "失敗"

    engagement = models.ForeignKey(
        "engagements.Engagement", on_delete=models.CASCADE, related_name="agent_runs"
    )
    trigger = models.CharField(max_length=20, choices=Trigger.choices)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.RUNNING)
    findings_count = models.PositiveSmallIntegerField("検知数", default=0)
    proposals_count = models.PositiveSmallIntegerField("提案数", default=0)
    error_message = models.TextField(blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-started_at"]

    def __str__(self) -> str:
        return f"{self.engagement.name} 巡回 @ {self.started_at:%Y-%m-%d %H:%M}"


class AgentProposal(models.Model):
    """承認待ちキューに積まれる提案。"""

    class Kind(models.TextChoices):
        REGISTER_RISK = "register_risk", "リスク登録"
        CREATE_ACTION = "create_action", "改善アクション作成"
        DRAFT_REPORT = "draft_report", "報告書ドラフト作成"
        SUMMARY_ONLY = "summary_only", "状況共有(登録なし)"

    class Status(models.TextChoices):
        PENDING = "pending", "承認待ち"
        APPROVED = "approved", "承認"
        REJECTED = "rejected", "却下"

    engagement = models.ForeignKey(
        "engagements.Engagement", on_delete=models.CASCADE, related_name="agent_proposals"
    )
    run = models.ForeignKey(AgentRun, on_delete=models.CASCADE, related_name="proposals")
    kind = models.CharField(max_length=30, choices=Kind.choices)
    dedup_key = models.CharField("重複抑止キー", max_length=100)
    title = models.CharField("提案", max_length=200)
    evidence = models.JSONField("検知根拠", default=dict)
    body = models.TextField("分析と提案内容", blank=True)
    payload = models.JSONField("承認時の登録データ", default=dict)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    decision_note = models.CharField("判断メモ", max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["engagement", "kind", "dedup_key"],
                condition=models.Q(status="pending"),
                name="unique_pending_proposal",
            )
        ]

    EVIDENCE_LABELS = {
        "observed": "検知値",
        "threshold": "しきい値",
        "window": "対象期間",
        "increment": "増加数",
        "open_count": "未クローズ数",
    }

    def __str__(self) -> str:
        return self.title

    @property
    def labeled_evidence(self) -> list[tuple[str, object]]:
        """検知根拠を日本語ラベル付きの (ラベル, 値) 一覧で返す。"""
        return [(self.EVIDENCE_LABELS.get(key, key), value) for key, value in self.evidence.items()]

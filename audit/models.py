from django.conf import settings
from django.db import models


class AuditLog(models.Model):
    """操作監査ログ。シグナルは使わず、記録ポイントから明示的に record() を呼ぶ。"""

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )
    action = models.CharField("操作", max_length=100)
    target_type = models.CharField("対象種別", max_length=100, blank=True)
    target_id = models.PositiveIntegerField("対象ID", null=True, blank=True)
    detail = models.CharField("詳細", max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    ACTION_LABELS = {
        "engagement_create": "案件を作成",
        "engagement_edit": "案件を編集",
        "engagement_delete": "案件を削除",
        "roadmap_project_initialized": "ロードマップ案件を初期化",
        "user_create": "ユーザーを作成",
        "token_create": "トークンを作成",
        "token_update": "トークンを更新",
        "token_delete": "トークンを削除",
        "odc_confirm": "ODC分類を確定",
        "report_approve": "報告書を承認",
        "test_plan_approve": "テスト計画を承認",
        "agent_proposal_approve": "エージェント提案を承認",
        "agent_proposal_reject": "エージェント提案を却下",
        "system_event": "システムイベント",
    }

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.action} {self.target_type}:{self.target_id}"

    @property
    def action_label(self) -> str:
        """操作コードを日本語表示に変換する（未知のコードはそのまま表示）。"""
        return self.ACTION_LABELS.get(self.action, self.action)

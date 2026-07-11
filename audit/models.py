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

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.action} {self.target_type}:{self.target_id}"

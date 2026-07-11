from django.conf import settings
from django.db import models


class MemberAlias(models.Model):
    """チケットのassignee_name(元システムの表示名)とシステムユーザーの対応表。"""

    engagement = models.ForeignKey(
        "engagements.Engagement", on_delete=models.CASCADE, related_name="member_aliases"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="member_aliases"
    )
    external_name = models.CharField("元システムの表示名", max_length=200)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["engagement", "external_name"], name="unique_alias_per_engagement"
            )
        ]

    def __str__(self) -> str:
        return f"{self.external_name} → {self.user}"

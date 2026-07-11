from django.conf import settings
from django.db import models


class UserPreference(models.Model):
    class Theme(models.TextChoices):
        AUTO = "auto", "システム設定に従う"
        LIGHT = "light", "ライト"
        DARK = "dark", "ダーク"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="preference"
    )
    theme = models.CharField(max_length=10, choices=Theme.choices, default=Theme.AUTO)

    def __str__(self) -> str:
        return f"{self.user}の設定"

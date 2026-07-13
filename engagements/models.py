from django.conf import settings
from django.db import models

from config.crypto import decrypt, encrypt


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
    # 空欄なら各プロバイダの環境変数の既定モデルを使う
    llm_model = models.CharField("既定モデル", max_length=100, blank=True)
    _llm_api_key_encrypted = models.TextField(
        "LLM APIキー(暗号化)", blank=True, db_column="llm_api_key_encrypted"
    )
    _llm_org_id_encrypted = models.TextField(
        "Organization ID(暗号化)", blank=True, db_column="llm_org_id_encrypted"
    )
    _llm_project_id_encrypted = models.TextField(
        "Project ID(暗号化)", blank=True, db_column="llm_project_id_encrypted"
    )
    # 種別マッピング: 元システムのticket_typeのうち欠陥として扱う値(大文字小文字は無視)
    defect_ticket_types = models.JSONField(
        "欠陥として扱う種別", default=list, blank=True
    )
    # 欠陥密度の分母(任意)。未入力なら欠陥密度は非表示
    size_metric_name = models.CharField(
        "規模の単位", max_length=50, blank=True, help_text="例: テストケース数, KLOC"
    )
    size_metric_value = models.DecimalField(
        "規模の値", max_digits=12, decimal_places=2, null=True, blank=True
    )
    # 案件ごとの月間トークン上限(0=無制限)。LLMコスト管理・暴走防止に使う。
    monthly_token_limit = models.PositiveIntegerField("月間トークン上限(0=無制限)", default=0)
    updated_at = models.DateTimeField("更新日時", auto_now=True)
    created_at = models.DateTimeField("作成日時", auto_now_add=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self) -> str:
        return self.name

    @property
    def member_count(self) -> int:
        return self.members.count()

    @property
    def llm_api_key(self) -> str:
        return decrypt(self._llm_api_key_encrypted)

    @llm_api_key.setter
    def llm_api_key(self, value: str) -> None:
        self._llm_api_key_encrypted = encrypt(value)

    @property
    def has_llm_api_key(self) -> bool:
        """APIキーを復号せずに設定有無だけを返す(F-6: 画面にキー材料を出さない)。"""
        return bool(self._llm_api_key_encrypted)

    @property
    def llm_org_id(self) -> str:
        return decrypt(self._llm_org_id_encrypted)

    @llm_org_id.setter
    def llm_org_id(self, value: str) -> None:
        self._llm_org_id_encrypted = encrypt(value)

    @property
    def has_llm_org_id(self) -> bool:
        return bool(self._llm_org_id_encrypted)

    @property
    def llm_project_id(self) -> str:
        return decrypt(self._llm_project_id_encrypted)

    @llm_project_id.setter
    def llm_project_id(self, value: str) -> None:
        self._llm_project_id_encrypted = encrypt(value)

    @property
    def has_llm_project_id(self) -> bool:
        return bool(self._llm_project_id_encrypted)


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

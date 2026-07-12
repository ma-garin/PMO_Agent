import time

from django.db.models import Count, F, Q, Sum

from .models import LlmCallLog
from .providers import LlmError, get_provider

__all__ = ["LlmError", "run_completion", "usage_summary", "test_connection"]

# 疎通確認で送る固定プロンプト。案件データを一切含めず、機密情報の送信を避ける。
_CONNECTIVITY_PROMPT = "ping"
_CONNECTIVITY_SYSTEM = "接続確認です。'pong'とだけ短く返答してください。"


def run_completion(
    engagement,
    purpose: str,
    prompt: str,
    *,
    system: str = "",
    max_tokens: int = 1024,
    user=None,
) -> str:
    provider_name = engagement.llm_provider
    model = getattr(engagement, "llm_model", "") or ""
    provider = get_provider(provider_name)
    started = time.monotonic()

    credential_kwargs = {}
    api_key = getattr(engagement, "llm_api_key", "") or ""
    if api_key and provider_name in ("openai", "claude"):
        credential_kwargs["api_key"] = api_key
    if provider_name == "openai":
        organization = getattr(engagement, "llm_org_id", "") or ""
        project = getattr(engagement, "llm_project_id", "") or ""
        if organization:
            credential_kwargs["organization"] = organization
        if project:
            credential_kwargs["project"] = project

    try:
        text = provider.complete(
            prompt, system=system, max_tokens=max_tokens, model=model, **credential_kwargs
        )
    except LlmError as exc:
        duration_ms = int((time.monotonic() - started) * 1000)
        LlmCallLog.objects.create(
            engagement=engagement,
            provider=provider_name,
            purpose=purpose,
            prompt_chars=len(prompt),
            response_chars=0,
            status=LlmCallLog.Status.FAILED,
            error_message=str(exc),
            duration_ms=duration_ms,
            created_by=user,
        )
        raise

    duration_ms = int((time.monotonic() - started) * 1000)
    LlmCallLog.objects.create(
        engagement=engagement,
        provider=provider_name,
        purpose=purpose,
        prompt_chars=len(prompt),
        response_chars=len(text),
        status=LlmCallLog.Status.SUCCESS,
        duration_ms=duration_ms,
        created_by=user,
    )
    return text


def test_connection(engagement, user=None) -> tuple[bool, str]:
    """保存済みのプロバイダ/モデルへ固定pingを送り、疎通可否を返す。

    案件データは送らない(固定プロンプト)。呼び出しはLlmCallLogに記録される。
    戻り値: (成功か, ユーザー向けメッセージ)。
    """
    try:
        response = run_completion(
            engagement,
            "connectivity_test",
            _CONNECTIVITY_PROMPT,
            system=_CONNECTIVITY_SYSTEM,
            max_tokens=16,
            user=user,
        )
    except LlmError as exc:
        return False, str(exc)
    snippet = (response or "").strip()[:60]
    return True, f"応答を受信しました: 「{snippet}」"


def usage_summary(year: int, month: int) -> list[dict]:
    """指定月の呼び出し実績を案件×プロバイダ×用途別に集計する。

    機密案件(engagement.llm_provider=ollama)なのに実際の呼び出しがクラウド
    プロバイダだった行には warning=True を立てる(呼び出し時のプロバイダ切替
    履歴やバグの検知用)。
    """
    logs = LlmCallLog.objects.filter(created_at__year=year, created_at__month=month)
    rows = (
        logs.values("engagement_id", "engagement__name", "engagement__llm_provider", "provider", "purpose")
        .annotate(
            call_count=Count("id"),
            total_chars=Sum(F("prompt_chars") + F("response_chars")),
            failure_count=Count("id", filter=Q(status=LlmCallLog.Status.FAILED)),
        )
        .order_by("engagement__name", "provider", "purpose")
    )

    result = []
    for row in rows:
        call_count = row["call_count"]
        failure_rate = round(row["failure_count"] / call_count * 100, 1) if call_count else 0.0
        is_confidential_leak = (
            row["engagement__llm_provider"] == "ollama" and row["provider"] != "ollama"
        )
        result.append(
            {
                "engagement_id": row["engagement_id"],
                "engagement_name": row["engagement__name"],
                "provider": row["provider"],
                "purpose": row["purpose"],
                "call_count": call_count,
                "total_chars": row["total_chars"] or 0,
                "failure_count": row["failure_count"],
                "failure_rate": failure_rate,
                "warning": is_confidential_leak,
            }
        )
    return result

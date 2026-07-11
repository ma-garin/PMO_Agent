import time

from django.db.models import Count, F, Q, Sum

from .models import LlmCallLog
from .providers import LlmError, get_provider

__all__ = ["LlmError", "run_completion", "usage_summary"]


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
    provider = get_provider(provider_name)
    started = time.monotonic()

    try:
        text = provider.complete(prompt, system=system, max_tokens=max_tokens)
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

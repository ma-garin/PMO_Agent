import time

from .models import LlmCallLog
from .providers import LlmError, get_provider

__all__ = ["LlmError", "run_completion"]


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

from .base import LlmError, LlmProvider
from .claude import ClaudeProvider
from .ollama import OllamaProvider
from .openai import OpenAiProvider

_PROVIDERS: dict[str, type[LlmProvider]] = {
    "claude": ClaudeProvider,
    "openai": OpenAiProvider,
    "ollama": OllamaProvider,
}


def get_provider(provider_name: str) -> LlmProvider:
    try:
        provider_class = _PROVIDERS[provider_name]
    except KeyError as exc:
        raise ValueError(f"未対応のLLMプロバイダです: {provider_name}") from exc
    return provider_class()


__all__ = [
    "LlmError",
    "LlmProvider",
    "ClaudeProvider",
    "OpenAiProvider",
    "OllamaProvider",
    "get_provider",
]

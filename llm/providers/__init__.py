from .base import LlmError, LlmProvider
from .claude import ClaudeProvider
from .ollama import OllamaProvider
from .openai import OpenAiProvider

_PROVIDERS: dict[str, type[LlmProvider]] = {
    "claude": ClaudeProvider,
    "openai": OpenAiProvider,
    "ollama": OllamaProvider,
}

# 画面のモデル選択肢(プロバイダ別)。空欄選択時は各providerの環境変数の既定を使う。
# ここに無いモデルも環境変数で指定すれば動作する(選択肢は代表例)。
MODEL_CHOICES: dict[str, list[str]] = {
    "openai": ["gpt-4o", "gpt-4o-mini"],
    "claude": ["claude-sonnet-5", "claude-haiku-4-5-20251001"],
    "ollama": ["qwen2.5:7b", "llama3.1:8b"],
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
    "MODEL_CHOICES",
    "get_provider",
]

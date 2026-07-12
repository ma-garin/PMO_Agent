import os

from .base import LlmError, LlmProvider
from .claude import ClaudeProvider
from .ollama import OllamaProvider
from .openai import OpenAiProvider

_PROVIDERS: dict[str, type[LlmProvider]] = {
    "claude": ClaudeProvider,
    "openai": OpenAiProvider,
    "ollama": OllamaProvider,
}


def _env_model_list(env_name: str, default: list[str]) -> list[str]:
    """カンマ区切りの環境変数があればそれを使い、無ければ既定値を返す。

    OpenAI等の現行モデル名はリリースごとに変わるため、コード改修なしで
    画面の選択肢を差し替えられるようにする。
    """
    raw = os.environ.get(env_name, "")
    values = [v.strip() for v in raw.split(",") if v.strip()]
    return values or default


# 画面のモデル選択肢(プロバイダ別)。空欄選択時は各providerの環境変数の既定を使う。
# ここに無いモデルも環境変数で指定すれば動作する(選択肢は代表例)。
MODEL_CHOICES: dict[str, list[str]] = {
    "openai": _env_model_list(
        "LLM_OPENAI_MODEL_CHOICES", ["gpt-5", "gpt-5-mini", "gpt-5-nano"]
    ),
    "claude": _env_model_list(
        "LLM_CLAUDE_MODEL_CHOICES",
        ["claude-opus-4-8", "claude-sonnet-5", "claude-haiku-4-5-20251001"],
    ),
    "ollama": _env_model_list(
        "LLM_OLLAMA_MODEL_CHOICES", ["qwen2.5:7b", "llama3.1:8b"]
    ),
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

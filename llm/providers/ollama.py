import os

import requests

from .base import LlmError, LlmProvider

REQUEST_TIMEOUT_SECONDS = 60


class OllamaProvider(LlmProvider):
    name = "ollama"

    def complete(
        self,
        prompt: str,
        *,
        system: str = "",
        max_tokens: int = 1024,
        model: str = "",
        api_key: str = "",
        organization: str = "",
        project: str = "",
    ) -> str:
        # ローカルLLMのため api_key/organization/project は使用しない(シグネチャ互換のみ)。
        base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
        model = model or os.environ.get("LLM_OLLAMA_MODEL", "qwen2.5:7b")
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        body = {"model": model, "stream": False, "messages": messages}

        try:
            response = requests.post(
                f"{base_url.rstrip('/')}/api/chat",
                json=body,
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
        except requests.ConnectionError as exc:
            raise LlmError(
                "Ollamaに接続できません。ollama serveが起動しているか確認してください"
            ) from exc
        except requests.RequestException as exc:
            raise LlmError(str(exc)) from exc

        payload = response.json()
        try:
            return payload["message"]["content"]
        except (KeyError, TypeError) as exc:
            raise LlmError(f"予期しない応答形式です: {payload}") from exc

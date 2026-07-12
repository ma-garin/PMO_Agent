import os

import requests

from .base import LlmError, LlmProvider

REQUEST_TIMEOUT_SECONDS = 60
API_URL = "https://api.anthropic.com/v1/messages"


class ClaudeProvider(LlmProvider):
    name = "claude"

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
        api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            raise LlmError("ANTHROPIC_API_KEYが未設定です。")

        model = model or os.environ.get("LLM_CLAUDE_MODEL", "claude-haiku-4-5-20251001")
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        body = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            body["system"] = system

        try:
            response = requests.post(
                API_URL, headers=headers, json=body, timeout=REQUEST_TIMEOUT_SECONDS
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise LlmError(str(exc)) from exc

        payload = response.json()
        try:
            return payload["content"][0]["text"]
        except (KeyError, IndexError) as exc:
            raise LlmError(f"予期しない応答形式です: {payload}") from exc

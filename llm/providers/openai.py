import os

import requests

from .base import LlmError, LlmProvider

REQUEST_TIMEOUT_SECONDS = 60
API_URL = "https://api.openai.com/v1/chat/completions"


class OpenAiProvider(LlmProvider):
    name = "openai"

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
        api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        if not api_key:
            raise LlmError("OPENAI_API_KEYが未設定です。")

        model = model or os.environ.get("LLM_OPENAI_MODEL", "gpt-5-mini")
        headers = {"Authorization": f"Bearer {api_key}"}
        organization = organization or os.environ.get("OPENAI_ORG_ID", "")
        project = project or os.environ.get("OPENAI_PROJECT_ID", "")
        if organization:
            headers["OpenAI-Organization"] = organization
        if project:
            headers["OpenAI-Project"] = project
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        body = {"model": model, "max_tokens": max_tokens, "messages": messages}

        try:
            response = requests.post(
                API_URL, headers=headers, json=body, timeout=REQUEST_TIMEOUT_SECONDS
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise LlmError(str(exc)) from exc

        payload = response.json()
        try:
            return payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as exc:
            raise LlmError(f"予期しない応答形式です: {payload}") from exc

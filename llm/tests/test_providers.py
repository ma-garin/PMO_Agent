import pytest
import responses

from llm.providers.base import LlmError
from llm.providers.claude import ClaudeProvider
from llm.providers.ollama import OllamaProvider
from llm.providers.openai import OpenAiProvider


@pytest.mark.unit
class TestClaudeProvider:
    @responses.activate
    def test_success(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        responses.add(
            responses.POST,
            "https://api.anthropic.com/v1/messages",
            json={"content": [{"text": "こんにちは"}]},
            status=200,
        )
        assert ClaudeProvider().complete("hi") == "こんにちは"

    def test_missing_key_raises(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        with pytest.raises(LlmError):
            ClaudeProvider().complete("hi")

    @responses.activate
    def test_non_200_raises(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        responses.add(
            responses.POST, "https://api.anthropic.com/v1/messages", status=500
        )
        with pytest.raises(LlmError):
            ClaudeProvider().complete("hi")

    @responses.activate
    def test_explicit_api_key_overrides_env(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "env-key")
        responses.add(
            responses.POST,
            "https://api.anthropic.com/v1/messages",
            json={"content": [{"text": "こんにちは"}]},
            status=200,
        )
        ClaudeProvider().complete("hi", api_key="explicit-key")
        assert responses.calls[0].request.headers["x-api-key"] == "explicit-key"

    @responses.activate
    def test_explicit_api_key_used_without_env(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        responses.add(
            responses.POST,
            "https://api.anthropic.com/v1/messages",
            json={"content": [{"text": "こんにちは"}]},
            status=200,
        )
        assert ClaudeProvider().complete("hi", api_key="explicit-key") == "こんにちは"


@pytest.mark.unit
class TestOpenAiProvider:
    @responses.activate
    def test_success(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        responses.add(
            responses.POST,
            "https://api.openai.com/v1/chat/completions",
            json={"choices": [{"message": {"content": "hello"}}]},
            status=200,
        )
        assert OpenAiProvider().complete("hi") == "hello"

    def test_missing_key_raises(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        with pytest.raises(LlmError):
            OpenAiProvider().complete("hi")

    @responses.activate
    def test_explicit_api_key_overrides_env(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "env-key")
        responses.add(
            responses.POST,
            "https://api.openai.com/v1/chat/completions",
            json={"choices": [{"message": {"content": "hello"}}]},
            status=200,
        )
        OpenAiProvider().complete("hi", api_key="explicit-key")
        assert responses.calls[0].request.headers["Authorization"] == "Bearer explicit-key"

    @responses.activate
    def test_organization_and_project_headers_sent_when_provided(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "env-key")
        monkeypatch.delenv("OPENAI_ORG_ID", raising=False)
        monkeypatch.delenv("OPENAI_PROJECT_ID", raising=False)
        responses.add(
            responses.POST,
            "https://api.openai.com/v1/chat/completions",
            json={"choices": [{"message": {"content": "hello"}}]},
            status=200,
        )
        OpenAiProvider().complete("hi", organization="org-123", project="proj-123")
        headers = responses.calls[0].request.headers
        assert headers["OpenAI-Organization"] == "org-123"
        assert headers["OpenAI-Project"] == "proj-123"

    @responses.activate
    def test_no_organization_or_project_headers_when_not_provided(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "env-key")
        monkeypatch.delenv("OPENAI_ORG_ID", raising=False)
        monkeypatch.delenv("OPENAI_PROJECT_ID", raising=False)
        responses.add(
            responses.POST,
            "https://api.openai.com/v1/chat/completions",
            json={"choices": [{"message": {"content": "hello"}}]},
            status=200,
        )
        OpenAiProvider().complete("hi")
        headers = responses.calls[0].request.headers
        assert "OpenAI-Organization" not in headers
        assert "OpenAI-Project" not in headers


@pytest.mark.unit
class TestOllamaProvider:
    @responses.activate
    def test_success(self, monkeypatch):
        monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434")
        responses.add(
            responses.POST,
            "http://localhost:11434/api/chat",
            json={"message": {"content": "やあ"}},
            status=200,
        )
        assert OllamaProvider().complete("hi") == "やあ"

    @responses.activate
    def test_connection_error_message(self, monkeypatch):
        import requests

        monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434")
        responses.add(
            responses.POST,
            "http://localhost:11434/api/chat",
            body=requests.ConnectionError("refused"),
        )
        with pytest.raises(LlmError, match="Ollamaに接続できません"):
            OllamaProvider().complete("hi")

    @responses.activate
    def test_accepts_and_ignores_cloud_credential_kwargs(self, monkeypatch):
        """他プロバイダ共通シグネチャ(api_key/organization/project)を受け取っても無視できること。"""
        monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434")
        responses.add(
            responses.POST,
            "http://localhost:11434/api/chat",
            json={"message": {"content": "やあ"}},
            status=200,
        )
        result = OllamaProvider().complete(
            "hi", api_key="unused", organization="unused", project="unused"
        )
        assert result == "やあ"

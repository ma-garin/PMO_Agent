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

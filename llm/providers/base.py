from abc import ABC, abstractmethod


class LlmError(Exception):
    pass


class LlmProvider(ABC):
    name: str = ""

    @abstractmethod
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
        """単発のテキスト補完。model指定時はそれを使い、空なら環境変数の既定。
        api_key/organization/project指定時はそれを優先し、空なら環境変数の既定を使う
        (ローカルLLM等、資格情報が不要なproviderは無視してよい)。失敗時はLlmError。
        """
        raise NotImplementedError

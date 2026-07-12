from abc import ABC, abstractmethod


class LlmError(Exception):
    pass


class LlmProvider(ABC):
    name: str = ""

    @abstractmethod
    def complete(
        self, prompt: str, *, system: str = "", max_tokens: int = 1024, model: str = ""
    ) -> str:
        """単発のテキスト補完。model指定時はそれを使い、空なら環境変数の既定。失敗時はLlmError。"""
        raise NotImplementedError

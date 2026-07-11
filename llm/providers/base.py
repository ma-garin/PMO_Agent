from abc import ABC, abstractmethod


class LlmError(Exception):
    pass


class LlmProvider(ABC):
    name: str = ""

    @abstractmethod
    def complete(self, prompt: str, *, system: str = "", max_tokens: int = 1024) -> str:
        """単発のテキスト補完。失敗時はLlmErrorをraise。"""
        raise NotImplementedError

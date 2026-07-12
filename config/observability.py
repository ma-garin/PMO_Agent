"""リクエストを横断して追跡するための軽量な可観測性基盤。"""

from __future__ import annotations

import json
import logging
import re
import uuid
from contextvars import ContextVar, Token
from datetime import UTC, datetime
from typing import Any

from asgiref.sync import iscoroutinefunction, markcoroutinefunction


REQUEST_ID_HEADER = "X-Request-ID"
_REQUEST_ID_RE = re.compile(r"\A[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)


def valid_request_id(value: str | None) -> bool:
    """ログ汚染を起こさない、長さを制限したASCIIのIDだけを許可する。"""

    return bool(value and _REQUEST_ID_RE.fullmatch(value))


def new_request_id() -> str:
    return uuid.uuid4().hex


def get_request_id() -> str | None:
    return _request_id.get()


def bind_request_id(value: str) -> Token[str | None]:
    return _request_id.set(value)


def reset_request_id(token: Token[str | None]) -> None:
    _request_id.reset(token)


class RequestIDMiddleware:
    """受信リクエストへ相関IDを割り当て、応答ヘッダーにも返す。"""

    sync_capable = True
    async_capable = True

    def __init__(self, get_response):
        self.get_response = get_response
        self.async_mode = iscoroutinefunction(get_response)
        if self.async_mode:
            markcoroutinefunction(self)

    def __call__(self, request):
        if self.async_mode:
            return self.__acall__(request)

        request_id = self._request_id_for(request)
        token = bind_request_id(request_id)
        request.request_id = request_id
        try:
            response = self.get_response(request)
            response[REQUEST_ID_HEADER] = request_id
            return response
        finally:
            reset_request_id(token)

    async def __acall__(self, request):
        request_id = self._request_id_for(request)
        token = bind_request_id(request_id)
        request.request_id = request_id
        try:
            response = await self.get_response(request)
            response[REQUEST_ID_HEADER] = request_id
            return response
        finally:
            reset_request_id(token)

    @staticmethod
    def _request_id_for(request) -> str:
        supplied = request.headers.get(REQUEST_ID_HEADER)
        return supplied if valid_request_id(supplied) else new_request_id()


class RequestContextFilter(logging.Filter):
    """既存のLogRecordへ相関IDを非破壊で追加する。"""

    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "request_id"):
            record.request_id = get_request_id() or "-"
        return True


class JsonFormatter(logging.Formatter):
    """運用基盤が解析しやすい1行JSON形式のフォーマッター。"""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", "-"),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))

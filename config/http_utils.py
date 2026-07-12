"""HTTPリクエスト由来の値を安全に扱うユーティリティ(F-4)。"""

from __future__ import annotations


def parse_int(value, default: int, minimum: int | None = None, maximum: int | None = None) -> int:
    """リクエスト値を安全にintへ変換する。非数値なら default を返し、範囲があればクランプ。"""
    try:
        result = int(value)
    except (TypeError, ValueError):
        return default
    if minimum is not None:
        result = max(minimum, result)
    if maximum is not None:
        result = min(maximum, result)
    return result


def parse_optional_number(value, *, as_float: bool):
    """数値文字列を int/float に変換する。空・非数値なら None を返す(条件付き設定値向け)。"""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return float(text) if as_float else int(text)
    except (TypeError, ValueError):
        return None

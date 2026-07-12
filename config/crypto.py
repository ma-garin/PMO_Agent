import logging
import os

from cryptography.fernet import Fernet, InvalidToken, MultiFernet

logger = logging.getLogger(__name__)


def _load_keys() -> list[str]:
    """暗号鍵を新しい順に返す。

    FIELD_ENCRYPTION_KEYS(カンマ区切り, 先頭=現行鍵)を優先し、
    後方互換で FIELD_ENCRYPTION_KEY(単一)も読む。鍵ローテーション時は
    "新鍵,旧鍵" と並べることで、旧鍵で暗号化された値も復号できる(F-14)。
    """
    multi = os.environ.get("FIELD_ENCRYPTION_KEYS", "")
    keys = [k.strip() for k in multi.split(",") if k.strip()]
    if not keys:
        single = os.environ.get("FIELD_ENCRYPTION_KEY", "").strip()
        if single:
            keys = [single]
    return keys


def _fernet() -> MultiFernet:
    keys = _load_keys()
    if not keys:
        raise RuntimeError(
            "FIELD_ENCRYPTION_KEY(S)が未設定です。.envに追加してください"
        )
    return MultiFernet([Fernet(k.encode()) for k in keys])


def encrypt(value: str) -> str:
    if not value:
        return value
    # MultiFernetは先頭(現行)鍵で暗号化する
    return _fernet().encrypt(value.encode()).decode()


def decrypt(value: str) -> str:
    if not value:
        return value
    try:
        # MultiFernetは登録された全鍵で復号を試みる(旧鍵の値も復号可)
        return _fernet().decrypt(value.encode()).decode()
    except InvalidToken:
        logger.warning("フィールドの復号に失敗しました(InvalidToken)")
        return ""

import pytest
from cryptography.fernet import Fernet

_TEST_ENCRYPTION_KEY = Fernet.generate_key().decode()


@pytest.fixture(autouse=True)
def _default_field_encryption_key(monkeypatch):
    """全テストでFIELD_ENCRYPTION_KEYを既定設定する。
    特定の鍵動作を検証するテストはmonkeypatchで個別に上書き・削除してよい。"""
    monkeypatch.setenv("FIELD_ENCRYPTION_KEY", _TEST_ENCRYPTION_KEY)

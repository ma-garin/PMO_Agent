import pytest
from cryptography.fernet import Fernet

from config.crypto import decrypt, encrypt

TEST_KEY = Fernet.generate_key().decode()


@pytest.mark.unit
class TestCrypto:
    def test_roundtrip(self, monkeypatch):
        monkeypatch.setenv("FIELD_ENCRYPTION_KEY", TEST_KEY)
        encrypted = encrypt("dummy-token-not-real")
        assert encrypted != "dummy-token-not-real"
        assert decrypt(encrypted) == "dummy-token-not-real"

    def test_empty_string_passthrough(self, monkeypatch):
        monkeypatch.setenv("FIELD_ENCRYPTION_KEY", TEST_KEY)
        assert encrypt("") == ""
        assert decrypt("") == ""

    def test_missing_key_raises(self, monkeypatch):
        monkeypatch.delenv("FIELD_ENCRYPTION_KEY", raising=False)
        with pytest.raises(RuntimeError):
            encrypt("value")

    def test_invalid_token_returns_empty_string(self, monkeypatch):
        monkeypatch.setenv("FIELD_ENCRYPTION_KEY", TEST_KEY)
        assert decrypt("not-a-valid-fernet-token") == ""

    def test_different_key_cannot_decrypt(self, monkeypatch):
        monkeypatch.setenv("FIELD_ENCRYPTION_KEY", TEST_KEY)
        encrypted = encrypt("secret")
        monkeypatch.setenv("FIELD_ENCRYPTION_KEY", Fernet.generate_key().decode())
        assert decrypt(encrypted) == ""

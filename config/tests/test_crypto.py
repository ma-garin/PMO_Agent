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


@pytest.mark.unit
class TestKeyRotation:
    """F-14: MultiFernetによる鍵ローテーション。"""

    def test_value_encrypted_with_old_key_decrypts_after_rotation(self, monkeypatch):
        old_key = Fernet.generate_key().decode()
        new_key = Fernet.generate_key().decode()

        # 旧鍵で暗号化
        monkeypatch.delenv("FIELD_ENCRYPTION_KEYS", raising=False)
        monkeypatch.setenv("FIELD_ENCRYPTION_KEY", old_key)
        encrypted = encrypt("secret-token")

        # ローテーション: 新鍵を先頭、旧鍵も併記
        monkeypatch.setenv("FIELD_ENCRYPTION_KEYS", f"{new_key},{old_key}")
        assert decrypt(encrypted) == "secret-token"

        # 再暗号化すると新鍵単独で復号できる
        re_encrypted = encrypt("secret-token")
        monkeypatch.setenv("FIELD_ENCRYPTION_KEYS", new_key)
        assert decrypt(re_encrypted) == "secret-token"

    def test_keys_env_takes_precedence_over_single_key(self, monkeypatch):
        key = Fernet.generate_key().decode()
        monkeypatch.setenv("FIELD_ENCRYPTION_KEYS", key)
        monkeypatch.setenv("FIELD_ENCRYPTION_KEY", "ignored-invalid")
        assert decrypt(encrypt("x")) == "x"

    def test_different_key_cannot_decrypt(self, monkeypatch):
        monkeypatch.setenv("FIELD_ENCRYPTION_KEY", TEST_KEY)
        encrypted = encrypt("secret")
        monkeypatch.setenv("FIELD_ENCRYPTION_KEY", Fernet.generate_key().decode())
        assert decrypt(encrypted) == ""

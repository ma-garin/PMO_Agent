"""F-13: SSRF内部アドレス遮断のテスト。"""

import pytest

from config.net_guard import is_safe_external_url


@pytest.mark.unit
class TestIsSafeExternalUrl:
    @pytest.mark.parametrize(
        "url",
        [
            "http://169.254.169.254/latest/meta-data/",  # クラウドメタデータ
            "http://127.0.0.1/admin",
            "https://localhost/x",
            "http://10.0.0.5/internal",
            "http://192.168.1.1/",
            "http://[::1]/",
            "https://foo.internal/",
            "http://0.0.0.0/",
        ],
    )
    def test_internal_addresses_are_blocked(self, url):
        assert is_safe_external_url(url) is False

    def test_public_domain_is_allowed(self):
        # 実在パブリックドメイン(解決できればpublic、解決失敗でも許可)
        assert is_safe_external_url("https://example.com/api") is True

    def test_unresolvable_host_is_allowed(self):
        # 解決できないホストは「不明」として許可(正当な外部URLの登録を妨げない)
        assert is_safe_external_url("https://nonexistent-host-xyz.example/") is True

    def test_non_http_scheme_rejected(self):
        assert is_safe_external_url("ftp://example.com/") is False
        assert is_safe_external_url("file:///etc/passwd") is False

    def test_empty_rejected(self):
        assert is_safe_external_url("") is False

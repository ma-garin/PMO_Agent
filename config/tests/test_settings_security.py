"""F-3: 本番セキュア設定のテスト(サブプロセスで設定モジュールの評価を検証)。"""

import os
import subprocess
import sys

import pytest

_SETUP = (
    "import django, os; "
    "os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings'); "
    "django.setup(); "
    "from django.conf import settings; "
)


def _run(code: str, env_extra: dict) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env.pop("DJANGO_SECRET_KEY", None)
    env.update(env_extra)
    return subprocess.run(
        [sys.executable, "-c", _SETUP + code],
        capture_output=True,
        text=True,
        env=env,
        cwd=os.getcwd(),
    )


@pytest.mark.unit
class TestProductionSecuritySettings:
    def test_production_without_secret_key_fails_fast(self):
        result = _run("print('LOADED')", {"DJANGO_DEBUG": "false"})
        assert result.returncode != 0
        assert "DJANGO_SECRET_KEY" in result.stderr

    def test_production_with_secret_key_enables_secure_flags(self):
        result = _run(
            "print(settings.SECURE_SSL_REDIRECT, settings.SESSION_COOKIE_SECURE, "
            "settings.CSRF_COOKIE_SECURE, settings.SECURE_HSTS_SECONDS)",
            {
                "DJANGO_DEBUG": "false",
                "DJANGO_SECRET_KEY": "prod-secret-key-value-abcdef1234567890",
                "DJANGO_ALLOWED_HOSTS": "pmo.example.com",
            },
        )
        assert result.returncode == 0, result.stderr
        assert "True True True 31536000" in result.stdout

    def test_development_does_not_force_https(self):
        result = _run(
            "print(getattr(settings, 'SECURE_SSL_REDIRECT', False))",
            {"DJANGO_DEBUG": "true"},
        )
        assert result.returncode == 0, result.stderr
        assert "False" in result.stdout

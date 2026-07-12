import pytest
from cryptography.fernet import Fernet
from django.contrib.auth.models import User
from django.core.management import call_command

from engagements.models import Engagement
from tickets.models import Ticket

TEST_KEY = Fernet.generate_key().decode()


@pytest.fixture(autouse=True)
def _encryption_key(monkeypatch):
    monkeypatch.setenv("FIELD_ENCRYPTION_KEY", TEST_KEY)


# テスト実行時 Django は DEBUG=False を強制するため、
# 「開発環境での投入」を検証するテストは settings.DEBUG=True を明示する(F-10のゲート回避)。
@pytest.mark.django_db
class TestSeedDemo:
    def test_running_twice_does_not_duplicate(self, settings):
        settings.DEBUG = True
        call_command("seed_demo")
        first_user_count = User.objects.count()
        first_engagement_count = Engagement.objects.count()
        first_ticket_count = Ticket.objects.count()

        call_command("seed_demo")

        assert first_user_count > 0
        assert User.objects.count() == first_user_count
        assert Engagement.objects.count() == first_engagement_count
        assert Ticket.objects.count() == first_ticket_count

    def test_creates_expected_users(self, settings):
        settings.DEBUG = True
        call_command("seed_demo")
        assert User.objects.filter(username="yuki").exists()
        assert User.objects.filter(username="admin", is_staff=True).exists()

    def test_admin_password_from_env(self, settings, monkeypatch):
        settings.DEBUG = True
        monkeypatch.setenv("SEED_ADMIN_PASSWORD", "custom-strong-pass-1234")
        call_command("seed_demo")
        admin = User.objects.get(username="admin")
        assert admin.check_password("custom-strong-pass-1234")


@pytest.mark.django_db
class TestSeedDemoProductionGuard:
    """F-10: 本番(DEBUG=False)での誤実行を防ぐゲート。"""

    def test_refused_in_production_without_force(self, settings):
        settings.DEBUG = False
        call_command("seed_demo")
        assert User.objects.count() == 0  # 本番では何も作られない

    def test_force_allows_production_run(self, settings):
        settings.DEBUG = False
        call_command("seed_demo", force=True)
        assert User.objects.filter(username="admin").exists()

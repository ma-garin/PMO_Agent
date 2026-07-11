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


@pytest.mark.django_db
class TestSeedDemo:
    def test_running_twice_does_not_duplicate(self):
        call_command("seed_demo")
        first_user_count = User.objects.count()
        first_engagement_count = Engagement.objects.count()
        first_ticket_count = Ticket.objects.count()

        call_command("seed_demo")

        assert User.objects.count() == first_user_count
        assert Engagement.objects.count() == first_engagement_count
        assert Ticket.objects.count() == first_ticket_count

    def test_creates_expected_users(self):
        call_command("seed_demo")
        assert User.objects.filter(username="yuki").exists()
        assert User.objects.filter(username="admin", is_staff=True).exists()

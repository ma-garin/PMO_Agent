import pytest
from cryptography.fernet import Fernet
from django.contrib.auth.models import User

from engagements.models import Engagement
from tickets.forms import TicketSourceForm

TEST_KEY = Fernet.generate_key().decode()


@pytest.fixture
def engagement(db) -> Engagement:
    owner = User.objects.create_user(username="pmo", password="x")
    return Engagement.objects.create(name="検証案件", owner=owner)


@pytest.fixture(autouse=True)
def _encryption_key(monkeypatch):
    monkeypatch.setenv("FIELD_ENCRYPTION_KEY", TEST_KEY)


@pytest.mark.django_db
class TestTicketSourceForm:
    def test_new_token_is_saved_and_encrypted(self, engagement):
        form = TicketSourceForm(
            data={
                "kind": "jira",
                "name": "JIRA",
                "base_url": "https://example.atlassian.net",
                "project_key": "T",
                "username": "user@example.com",
                "api_token": "raw-token-value",
                "is_active": True,
            }
        )
        assert form.is_valid(), form.errors
        source = form.save(commit=False)
        source.engagement = engagement
        source.save()

        assert source.api_token == "raw-token-value"
        assert "raw-token-value" not in source._api_token_encrypted

    def test_blank_token_keeps_existing_value(self, engagement):
        from tickets.models import TicketSource

        existing = TicketSource.objects.create(
            engagement=engagement,
            kind="jira",
            name="JIRA",
            base_url="https://example.atlassian.net",
            project_key="T",
        )
        existing.api_token = "original-token"
        existing.save()

        form = TicketSourceForm(
            data={
                "kind": "jira",
                "name": "JIRA(更新)",
                "base_url": "https://example.atlassian.net",
                "project_key": "T",
                "username": "",
                "api_token": "",
                "is_active": True,
            },
            instance=existing,
        )
        assert form.is_valid(), form.errors
        saved = form.save()
        assert saved.api_token == "original-token"

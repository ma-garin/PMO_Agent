"""F-12: LLMプロバイダ変更の管理者限定化テスト。"""

import pytest
from django.contrib.auth.models import User

from engagements.models import Engagement


@pytest.fixture
def general_user(db) -> User:
    return User.objects.create_user(username="member", password="x", is_staff=False)


@pytest.fixture
def admin_user(db) -> User:
    return User.objects.create_user(username="admin", password="x", is_staff=True)


def _engagement_for(user) -> Engagement:
    e = Engagement.objects.create(name="機密案件", owner=user, llm_provider="ollama")
    e.members.add(user)
    return e


def _login_with_engagement(client, user, engagement):
    client.force_login(user)
    session = client.session
    session["current_engagement_id"] = engagement.pk
    session.save()


@pytest.mark.django_db
class TestLlmSettingsPermission:
    def test_member_cannot_change_provider(self, client, general_user):
        engagement = _engagement_for(general_user)
        _login_with_engagement(client, general_user, engagement)

        client.post("/engagements/settings/llm/", {"llm_provider": "openai"})

        engagement.refresh_from_db()
        assert engagement.llm_provider == "ollama"  # クラウドに切り替わっていない

    def test_member_can_view_but_form_is_hidden(self, client, general_user):
        engagement = _engagement_for(general_user)
        _login_with_engagement(client, general_user, engagement)

        response = client.get("/engagements/settings/llm/")
        assert response.status_code == 200
        assert response.context["can_edit"] is False

    def test_admin_can_change_provider(self, client, admin_user):
        engagement = _engagement_for(admin_user)
        _login_with_engagement(client, admin_user, engagement)

        client.post("/engagements/settings/llm/", {"llm_provider": "claude"})

        engagement.refresh_from_db()
        assert engagement.llm_provider == "claude"

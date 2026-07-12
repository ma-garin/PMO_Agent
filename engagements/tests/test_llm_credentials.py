"""案件ごとのLLM APIキー/Organization ID/Project IDの暗号化保存のテスト。"""

import pytest

from engagements.models import Engagement


@pytest.fixture
def owner(django_user_model):
    return django_user_model.objects.create_user(username="owner", password="x")


@pytest.mark.django_db
class TestLlmApiKeyEncryption:
    def test_api_key_round_trips_through_property(self, owner):
        engagement = Engagement.objects.create(name="案件", owner=owner)
        engagement.llm_api_key = "sk-secret-value"
        engagement.save()

        engagement.refresh_from_db()
        assert engagement.llm_api_key == "sk-secret-value"

    def test_api_key_is_encrypted_at_rest(self, owner):
        engagement = Engagement.objects.create(name="案件", owner=owner)
        engagement.llm_api_key = "sk-secret-value"
        engagement.save()

        # DBカラムには平文が入らないこと(F-6と同様の方針)
        assert "sk-secret-value" not in engagement._llm_api_key_encrypted
        assert engagement._llm_api_key_encrypted != ""

    def test_has_llm_api_key_true_when_set(self, owner):
        engagement = Engagement.objects.create(name="案件", owner=owner)
        assert engagement.has_llm_api_key is False

        engagement.llm_api_key = "sk-secret-value"
        assert engagement.has_llm_api_key is True

    def test_blank_api_key_is_falsy(self, owner):
        engagement = Engagement.objects.create(name="案件", owner=owner)
        engagement.llm_api_key = ""
        assert engagement.llm_api_key == ""
        assert engagement.has_llm_api_key is False

    def test_org_id_round_trips_through_property(self, owner):
        engagement = Engagement.objects.create(name="案件", owner=owner)
        engagement.llm_org_id = "org-123"
        engagement.save()

        engagement.refresh_from_db()
        assert engagement.llm_org_id == "org-123"
        assert "org-123" not in engagement._llm_org_id_encrypted

    def test_project_id_round_trips_through_property(self, owner):
        engagement = Engagement.objects.create(name="案件", owner=owner)
        engagement.llm_project_id = "proj-123"
        engagement.save()

        engagement.refresh_from_db()
        assert engagement.llm_project_id == "proj-123"
        assert "proj-123" not in engagement._llm_project_id_encrypted

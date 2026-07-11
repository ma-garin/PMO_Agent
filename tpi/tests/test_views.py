import pytest
from django.contrib.auth.models import User
from django.test import Client

from engagements.models import Engagement
from tpi.models import TpiAnswer, TpiAssessment, TpiCheckpoint, TpiKeyArea


@pytest.fixture
def user(db) -> User:
    return User.objects.create_user(username="pmo", password="x")


@pytest.fixture
def engagement(user) -> Engagement:
    e = Engagement.objects.create(name="検証案件", owner=user)
    e.members.add(user)
    return e


@pytest.fixture
def logged_in_client(client: Client, user, engagement) -> Client:
    client.force_login(user)
    session = client.session
    session["current_engagement_id"] = engagement.pk
    session.save()
    return client


@pytest.fixture
def key_area(db) -> TpiKeyArea:
    return TpiKeyArea.objects.create(name="テスト戦略")


@pytest.mark.django_db
class TestAnswerAndFinalize:
    def test_answer_saved_via_upsert(self, logged_in_client, engagement, user, key_area):
        checkpoint = TpiCheckpoint.objects.create(key_area=key_area, level="controlled", text="c1")
        assessment = TpiAssessment.objects.create(engagement=engagement, title="評価1", assessed_by=user)

        logged_in_client.post(
            f"/tpi/{assessment.pk}/answer/{key_area.pk}/",
            {f"result_{checkpoint.pk}": "met", f"note_{checkpoint.pk}": "確認済み"},
        )
        answer = TpiAnswer.objects.get(assessment=assessment, checkpoint=checkpoint)
        assert answer.result == "met"
        assert answer.note == "確認済み"

    def test_finalized_assessment_rejects_further_answers(
        self, logged_in_client, engagement, user, key_area
    ):
        checkpoint = TpiCheckpoint.objects.create(key_area=key_area, level="controlled", text="c1")
        assessment = TpiAssessment.objects.create(
            engagement=engagement, title="評価1", assessed_by=user, status=TpiAssessment.Status.FINAL
        )
        logged_in_client.post(
            f"/tpi/{assessment.pk}/answer/{key_area.pk}/", {f"result_{checkpoint.pk}": "met"}
        )
        assert not TpiAnswer.objects.filter(assessment=assessment, checkpoint=checkpoint).exists()

    def test_other_engagement_assessment_is_404(self, logged_in_client):
        other_owner = User.objects.create_user(username="other", password="x")
        other_engagement = Engagement.objects.create(name="他案件", owner=other_owner)
        other_assessment = TpiAssessment.objects.create(
            engagement=other_engagement, title="他評価", assessed_by=other_owner
        )
        response = logged_in_client.get(f"/tpi/{other_assessment.pk}/")
        assert response.status_code == 404

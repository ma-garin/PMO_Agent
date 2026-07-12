"""ヘッダーに現在の案件名を出す context processor のテスト。"""

import pytest
from django.contrib.auth.models import User
from django.test import Client

from engagements.models import Engagement


@pytest.mark.django_db
class TestCurrentEngagementContext:
    def test_engagement_name_appears_in_header(self, client: Client):
        user = User.objects.create_user(username="pmo", password="x")
        engagement = Engagement.objects.create(name="基幹システム刷新", owner=user)
        engagement.members.add(user)
        client.force_login(user)
        session = client.session
        session["current_engagement_id"] = engagement.pk
        session.save()

        response = client.get("/dashboard/")
        assert response.status_code == 200
        assert response.context["current_engagement_name"] == "基幹システム刷新"
        assert "基幹システム刷新".encode() in response.content

    def test_no_engagement_selected_is_blank(self, client: Client):
        user = User.objects.create_user(username="pmo2", password="x")
        client.force_login(user)
        # 案件未選択(セッションに無い) → 空
        response = client.get("/engagements/")
        assert response.context["current_engagement_name"] == ""

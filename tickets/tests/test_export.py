import pytest
from django.contrib.auth.models import User
from django.test import Client

from engagements.models import Engagement
from tickets.models import Ticket, TicketSource


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


@pytest.mark.django_db
class TestTicketExportCsv:
    def test_response_is_csv_with_bom_and_expected_rows(self, logged_in_client, engagement):
        source = TicketSource.objects.create(
            engagement=engagement, kind="jira", name="s", base_url="https://x", project_key="P"
        )
        Ticket.objects.create(source=source, external_id="T-1", summary="サンプルチケット")

        response = logged_in_client.get("/tickets/export.csv")
        assert response.status_code == 200
        assert response["Content-Type"].startswith("text/csv")
        content = b"".join(response.streaming_content).decode("utf-8")
        assert content.startswith("﻿")
        assert "T-1" in content
        assert "サンプルチケット" in content

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
    e = Engagement.objects.create(name="検証案件アルファ", owner=user)
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
class TestSearch:
    def test_empty_query_shows_empty_state(self, logged_in_client):
        response = logged_in_client.get("/search/")
        assert response.context["groups"] == []

    def test_ticket_scoped_to_current_engagement(self, logged_in_client, engagement, user):
        other = Engagement.objects.create(name="他案件", owner=user)
        source_a = TicketSource.objects.create(
            engagement=engagement, kind="jira", name="a", base_url="https://x", project_key="P"
        )
        source_b = TicketSource.objects.create(
            engagement=other, kind="jira", name="b", base_url="https://x", project_key="P"
        )
        Ticket.objects.create(source=source_a, external_id="1", summary="対象チケットの検証")
        Ticket.objects.create(source=source_b, external_id="2", summary="対象チケットの検証(他案件)")

        response = logged_in_client.get("/search/?q=対象チケット")
        ticket_group = next(g for g in response.context["groups"] if g["label"] == "チケット")
        assert len(ticket_group["items"]) == 1

    def test_engagement_name_search(self, logged_in_client):
        response = logged_in_client.get("/search/?q=アルファ")
        engagement_group = next(g for g in response.context["groups"] if g["label"] == "案件")
        assert len(engagement_group["items"]) == 1

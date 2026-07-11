import pytest
from django.contrib.auth.models import User
from django.test import Client

from engagements.models import Engagement
from members.models import MemberAlias
from tickets.models import Ticket, TicketSource


@pytest.fixture
def owner(db) -> User:
    return User.objects.create_user(username="owner", password="x")


@pytest.fixture
def engagement(owner) -> Engagement:
    e = Engagement.objects.create(name="検証案件", owner=owner)
    e.members.add(owner)
    return e


@pytest.fixture
def logged_in_client(client: Client, owner, engagement) -> Client:
    client.force_login(owner)
    session = client.session
    session["current_engagement_id"] = engagement.pk
    session.save()
    return client


@pytest.mark.django_db
class TestMemberList:
    def test_ticket_counts_via_alias(self, logged_in_client, engagement, owner):
        source = TicketSource.objects.create(
            engagement=engagement, kind="jira", name="s", base_url="https://x", project_key="P"
        )
        Ticket.objects.create(source=source, external_id="1", summary="a", assignee_name="藤曲", is_done=False)
        Ticket.objects.create(source=source, external_id="2", summary="b", assignee_name="藤曲", is_done=True)
        MemberAlias.objects.create(engagement=engagement, user=owner, external_name="藤曲")

        response = logged_in_client.get("/members/")
        row = response.context["member_rows"][0]
        assert row["total"] == 2
        assert row["open"] == 1

    def test_unmapped_assignee_names_are_listed(self, logged_in_client, engagement):
        source = TicketSource.objects.create(
            engagement=engagement, kind="jira", name="s", base_url="https://x", project_key="P"
        )
        Ticket.objects.create(source=source, external_id="1", summary="a", assignee_name="未対応の担当者")

        response = logged_in_client.get("/members/")
        assert "未対応の担当者" in response.context["unmapped_names"]

import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.utils import timezone

from engagements.models import Engagement
from engagements.views import portfolio_stats
from tickets.models import Notification, Ticket, TicketSource


@pytest.fixture
def owner(db) -> User:
    return User.objects.create_user(username="owner", password="x")


@pytest.fixture
def general_user(db) -> User:
    return User.objects.create_user(username="general", password="x")


@pytest.fixture
def admin(db) -> User:
    return User.objects.create_user(username="admin2", password="x", is_staff=True)


@pytest.mark.django_db
class TestPortfolioStats:
    def test_open_and_overdue_counts_are_correct(self, owner):
        engagement = Engagement.objects.create(name="案件A", owner=owner)
        source = TicketSource.objects.create(
            engagement=engagement, kind="jira", name="s", base_url="https://x", project_key="P"
        )
        today = timezone.localdate()
        Ticket.objects.create(source=source, external_id="1", summary="a", is_done=False, due_date=today)
        Ticket.objects.create(
            source=source, external_id="2", summary="b", is_done=False,
            due_date=today - timezone.timedelta(days=3),
        )
        Ticket.objects.create(source=source, external_id="3", summary="c", is_done=True)

        stats = portfolio_stats([engagement.pk])
        assert stats[engagement.pk]["open"] == 2
        assert stats[engagement.pk]["overdue"] == 1

    def test_unread_notification_count(self, owner):
        engagement = Engagement.objects.create(name="案件B", owner=owner)
        source = TicketSource.objects.create(
            engagement=engagement, kind="jira", name="s", base_url="https://x", project_key="P"
        )
        ticket = Ticket.objects.create(source=source, external_id="1", summary="a")
        Notification.objects.create(engagement=engagement, ticket=ticket, kind="stagnant", message="m", is_read=False)
        Notification.objects.create(engagement=engagement, ticket=ticket, kind="overdue", message="m2", is_read=True)

        stats = portfolio_stats([engagement.pk])
        assert stats[engagement.pk]["unread"] == 1


@pytest.mark.django_db
class TestEngagementSelectVisibility:
    def test_general_user_only_sees_own_engagements(self, general_user, owner):
        mine = Engagement.objects.create(name="自分の案件", owner=general_user)
        mine.members.add(general_user)
        Engagement.objects.create(name="他人の案件", owner=owner)

        client = Client()
        client.force_login(general_user)
        response = client.get("/engagements/")
        names = [e.name for e in response.context["engagements"]]
        assert names == ["自分の案件"]

    def test_admin_sees_all_engagements_with_non_member_flag(self, admin, owner):
        Engagement.objects.create(name="他人の案件", owner=owner)

        client = Client()
        client.force_login(admin)
        response = client.get("/engagements/")
        engagements = response.context["engagements"]
        names = [e.name for e in engagements]
        assert "他人の案件" in names
        other = next(e for e in engagements if e.name == "他人の案件")
        assert other.is_non_member is True

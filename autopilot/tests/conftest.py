import pytest
from django.contrib.auth.models import User

from engagements.models import Engagement
from tickets.models import TicketSource


@pytest.fixture
def owner(db) -> User:
    return User.objects.create_user(username="pmo", password="x")


@pytest.fixture
def engagement(owner) -> Engagement:
    e = Engagement.objects.create(name="検証案件", owner=owner)
    e.members.add(owner)
    return e


@pytest.fixture
def source(engagement) -> TicketSource:
    return TicketSource.objects.create(
        engagement=engagement, kind="jira", name="s", base_url="https://x", project_key="P"
    )

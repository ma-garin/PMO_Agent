from __future__ import annotations

import pytest
from django.contrib.auth.models import User

from engagements.models import Engagement
from tickets.models import TicketSource


@pytest.fixture
def user(db) -> User:
    return User.objects.create_user(username="pm-user", password="pass12345")  # noqa: S106


@pytest.fixture
def engagement(user: User) -> Engagement:
    return Engagement.objects.create(name="テスト案件", owner=user)


@pytest.fixture
def ticket_source(engagement: Engagement) -> TicketSource:
    return TicketSource.objects.create(
        engagement=engagement,
        kind=TicketSource.Kind.JIRA,
        name="JIRA連携",
        base_url="https://example.atlassian.net",
        project_key="PROJ",
        username="user@example.com",
        api_token="dummy-token",
    )

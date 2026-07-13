import json

import pytest
from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import Client
from django.urls import reverse

from engagements.models import Engagement


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def api_client(client: Client, db) -> Client:
    user = User.objects.create_user(username="pmo", password="x")
    engagement = Engagement.objects.create(name="検証案件", owner=user)
    engagement.members.add(user)
    client.force_login(user)
    session = client.session
    session["current_engagement_id"] = engagement.pk
    session.save()
    return client


@pytest.mark.django_db
def test_stores_post_is_rate_limited(api_client: Client):
    url = reverse("pmo_agent:stores_api", args=["report"])
    statuses = [
        api_client.post(url, json.dumps({"n": i}), content_type="application/json").status_code
        for i in range(42)
    ]
    assert statuses[:40] == [200] * 40
    assert 429 in statuses[40:]


@pytest.mark.django_db
def test_get_is_not_rate_limited(api_client: Client):
    url = reverse("pmo_agent:tasks_api")
    assert all(api_client.get(url).status_code == 200 for _ in range(50))

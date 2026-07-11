import pytest
from django.contrib.auth.models import User
from django.test import Client

from engagements.models import Engagement


@pytest.fixture
def engagement(db) -> Engagement:
    owner = User.objects.create_user(username="pmo", password="x")
    e = Engagement.objects.create(name="検証案件", owner=owner)
    e.members.add(owner)
    return e


@pytest.mark.django_db
class TestSidebarCollapse:
    def test_sidebar_renders_toggle_button_and_collapsible_id(self, client: Client, engagement):
        client.force_login(engagement.owner)
        session = client.session
        session["current_engagement_id"] = engagement.pk
        session.save()

        response = client.get("/dashboard/")

        assert response.status_code == 200
        content = response.content.decode()
        assert 'id="app-sidebar"' in content
        assert 'id="sidebar-toggle"' in content
        assert 'class="nav-label"' in content

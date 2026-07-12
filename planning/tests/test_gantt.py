from datetime import date, timedelta

import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse

from engagements.models import Engagement
from planning.models import Schedule, WorkItem
from planning.services import gantt_chart_data


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
class TestGanttChartData:
    def test_empty_schedule_returns_empty_geometry(self, engagement):
        schedule = Schedule.objects.create(engagement=engagement, status_date=date.today())
        chart = gantt_chart_data(schedule)
        assert chart["bars"] == []
        assert chart["progress_line"] == ""

    def test_bars_are_ordered_and_within_chart_width(self, engagement):
        schedule = Schedule.objects.create(engagement=engagement, status_date=date.today())
        today = date.today()
        WorkItem.objects.create(
            schedule=schedule, wbs_code="1", title="A",
            start_date=today, finish_date=today + timedelta(days=5), progress=100,
        )
        WorkItem.objects.create(
            schedule=schedule, wbs_code="2", title="B",
            start_date=today + timedelta(days=3), finish_date=today + timedelta(days=10), progress=0,
        )
        chart = gantt_chart_data(schedule)
        assert len(chart["bars"]) == 2
        for bar in chart["bars"]:
            assert 0 <= bar["x"] <= chart["width"]
            assert bar["x"] + bar["width"] <= chart["width"] + 6  # マイルストーン等の最小幅マージン

    def test_progress_line_has_one_point_per_item(self, engagement):
        schedule = Schedule.objects.create(engagement=engagement, status_date=date.today())
        today = date.today()
        for i in range(3):
            WorkItem.objects.create(
                schedule=schedule, wbs_code=str(i + 1), title=f"item{i}",
                start_date=today, finish_date=today + timedelta(days=2), progress=50,
            )
        chart = gantt_chart_data(schedule)
        assert len(chart["progress_line"].split(" ")) == 3

    def test_today_line_none_when_outside_range(self, engagement):
        schedule = Schedule.objects.create(engagement=engagement, status_date=date.today())
        past = date.today() - timedelta(days=30)
        WorkItem.objects.create(
            schedule=schedule, wbs_code="1", title="past task",
            start_date=past, finish_date=past + timedelta(days=2), progress=100,
        )
        chart = gantt_chart_data(schedule)
        assert chart["today_x"] is None


@pytest.mark.django_db
class TestGanttView:
    def test_no_schedule_shows_empty_state(self, logged_in_client):
        response = logged_in_client.get(reverse("planning:gantt"))
        assert response.status_code == 200
        assert "WBSが未登録です".encode() in response.content

    def test_schedule_with_items_renders_wbs_table(self, logged_in_client, engagement):
        schedule = Schedule.objects.create(engagement=engagement, status_date=date.today())
        WorkItem.objects.create(
            schedule=schedule, wbs_code="1", title="要件定義",
            start_date=date.today(), finish_date=date.today() + timedelta(days=3), progress=40,
        )
        response = logged_in_client.get(reverse("planning:gantt"))
        assert response.status_code == 200
        assert "要件定義".encode() in response.content
        assert b"40%" in response.content

    def test_no_engagement_redirects_to_select(self, client: Client, user):
        client.force_login(user)
        response = client.get(reverse("planning:gantt"))
        assert response.status_code == 302
        assert response.url == reverse("engagements:select")

    def test_other_engagement_schedule_is_not_visible(self, logged_in_client, user):
        other_owner = User.objects.create_user(username="other", password="x")
        other_engagement = Engagement.objects.create(name="他案件", owner=other_owner)
        Schedule.objects.create(engagement=other_engagement, status_date=date.today())

        response = logged_in_client.get(reverse("planning:gantt"))
        assert response.status_code == 200
        assert "WBSが未登録です".encode() in response.content

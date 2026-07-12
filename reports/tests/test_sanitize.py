"""F-2: 報告書Markdownの無害化(保存型XSS対策)のテスト。"""

from unittest.mock import patch

import pytest
from django.contrib.auth.models import User
from django.test import Client

from engagements.models import Engagement
from reports.models import Report
from reports.services import render_markdown_safe


@pytest.mark.unit
class TestRenderMarkdownSafe:
    def test_script_tag_is_stripped(self):
        out = render_markdown_safe("正常な文<script>alert(1)</script>")
        assert "<script>" not in out.lower()
        assert "alert(1)" not in out or "<script" not in out.lower()

    def test_javascript_scheme_link_is_neutralized(self):
        out = render_markdown_safe("[クリック](javascript:alert(1))")
        assert "javascript:" not in out.lower()

    def test_event_handler_attribute_is_removed(self):
        out = render_markdown_safe('<img src=x onerror="alert(1)">')
        assert "onerror" not in out.lower()

    def test_legit_markdown_is_converted(self):
        out = render_markdown_safe("# 見出し\n\n**強調** と normal")
        assert "<h1>" in out
        assert "見出し" in out
        assert "<strong>強調</strong>" in out

    def test_table_extension_works(self):
        md = "| A | B |\n|---|---|\n| 1 | 2 |"
        out = render_markdown_safe(md)
        assert "<table>" in out
        assert "<td>1</td>" in out

    def test_empty_and_none_are_safe(self):
        assert render_markdown_safe("") == ""
        assert render_markdown_safe(None) == ""


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
class TestReportViewSanitization:
    def test_edit_preview_does_not_contain_script(self, logged_in_client, engagement, user):
        report = Report.objects.create(
            engagement=engagement,
            title="悪意ある報告書",
            period_start="2026-07-01",
            period_end="2026-07-31",
            body="正常\n\n<script>document.location='http://evil'</script>",
            created_by=user,
        )
        response = logged_in_client.get(f"/reports/{report.pk}/")
        assert response.status_code == 200
        assert b"<script>" not in response.content

    def test_print_view_does_not_contain_script(self, logged_in_client, engagement, user):
        report = Report.objects.create(
            engagement=engagement,
            title="悪意ある報告書",
            period_start="2026-07-01",
            period_end="2026-07-31",
            body="<script>alert(1)</script>",
            created_by=user,
        )
        response = logged_in_client.get(f"/reports/{report.pk}/print/")
        assert response.status_code == 200
        assert b"<script>" not in response.content

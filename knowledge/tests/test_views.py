from unittest.mock import patch

import pytest
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client

from engagements.models import Engagement
from knowledge.models import Document


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
class TestUpload:
    def test_upload_creates_document_and_defers_processing(self, logged_in_client):
        upload_file = SimpleUploadedFile("standard.md", b"# content", content_type="text/markdown")
        with patch("knowledge.views.process_document") as mock_task:
            logged_in_client.post(
                "/knowledge/upload/",
                {"title": "開発標準", "file": upload_file, "scope": "engagement"},
            )
        mock_task.defer.assert_called_once()
        assert Document.objects.filter(title="開発標準").exists()

    def test_upload_over_size_limit_is_rejected(self, logged_in_client):
        big_content = b"a" * (11 * 1024 * 1024)
        upload_file = SimpleUploadedFile("big.txt", big_content, content_type="text/plain")
        with patch("knowledge.views.process_document") as mock_task:
            logged_in_client.post("/knowledge/upload/", {"file": upload_file, "scope": "engagement"})
        mock_task.defer.assert_not_called()
        assert not Document.objects.exists()


def _make_document(engagement, title="資料"):
    return Document.objects.create(
        engagement=engagement,
        title=title,
        file=SimpleUploadedFile(f"{title}.md", b"# x", content_type="text/markdown"),
    )


@pytest.mark.django_db
class TestDeleteScope:
    """F-1: 削除・再取込が案件スコープで保護されているか。"""

    def test_own_engagement_document_can_be_deleted(self, logged_in_client, engagement):
        doc = _make_document(engagement)
        logged_in_client.post(f"/knowledge/{doc.pk}/delete/")
        assert not Document.objects.filter(pk=doc.pk).exists()

    def test_other_engagement_document_is_404_and_survives(self, logged_in_client, user):
        other_engagement = Engagement.objects.create(name="別案件", owner=user)
        other_doc = _make_document(other_engagement, title="他案件資料")
        response = logged_in_client.post(f"/knowledge/{other_doc.pk}/delete/")
        assert response.status_code == 404
        assert Document.objects.filter(pk=other_doc.pk).exists()

    def test_other_engagement_document_reindex_is_404(self, logged_in_client, user):
        other_engagement = Engagement.objects.create(name="別案件", owner=user)
        other_doc = _make_document(other_engagement, title="他案件資料")
        with patch("knowledge.views.process_document") as mock_task:
            response = logged_in_client.post(f"/knowledge/{other_doc.pk}/reindex/")
        assert response.status_code == 404
        mock_task.defer.assert_not_called()

    def test_common_document_delete_requires_staff(self, logged_in_client, engagement):
        common_doc = _make_document(None, title="共通資料")  # engagement=None
        response = logged_in_client.post(f"/knowledge/{common_doc.pk}/delete/")
        # 一般ユーザーは共通資料を削除できない(可視だが拒否される)
        assert response.status_code == 302
        assert Document.objects.filter(pk=common_doc.pk).exists()

    def test_staff_can_delete_common_document(self, client, user, engagement):
        user.is_staff = True
        user.save(update_fields=["is_staff"])
        client.force_login(user)
        session = client.session
        session["current_engagement_id"] = engagement.pk
        session.save()
        common_doc = _make_document(None, title="共通資料")
        client.post(f"/knowledge/{common_doc.pk}/delete/")
        assert not Document.objects.filter(pk=common_doc.pk).exists()

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
